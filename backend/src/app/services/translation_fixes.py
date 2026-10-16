"""Decide and store translation proposals."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.admin_validators import MAX_DESCRIPTION_LENGTH, MAX_NAME_LENGTH
from app.db.models import Activity, Organization
from app.db.models.translation_fix import TranslationFixProposal
from app.db.repositories import OrganizationRepository
from app.exceptions import NotFoundError, ValidationError
from app.services.translation_fix_query import (
    ENTITY_TYPES,
    FIELDS,
    filtered_stmt,
    pending_row,
    serialize_many,
)
from app.services.translation_gaps import (
    LANGUAGES,
    entity_gaps,
    source_hash,
    text_value,
)

_MAX_BULK = 200


def decide_proposal(
    session: Session,
    proposal_id: UUID,
    action: str,
    decided_by: str | None,
    *,
    translations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = session.get(TranslationFixProposal, proposal_id)
    if row is None:
        raise NotFoundError("translation_fix_proposals", str(proposal_id))
    if row.status != "pending":
        raise ValidationError("Proposal is already decided", field="status")
    if action == "dismiss":
        _mark(row, "dismissed", decided_by)
        session.flush()
        return serialize_many(session, [row])[0]
    if action != "apply":
        raise ValidationError("action must be apply or dismiss", field="action")
    apply_proposal(session, row, translations=translations)
    _mark(row, "applied", decided_by)
    session.flush()
    return serialize_many(session, [row])[0]


def decide_bulk(
    session: Session, body: dict[str, Any], decided_by: str | None
) -> dict[str, Any]:
    action = body.get("action")
    if action not in {"apply", "dismiss"}:
        raise ValidationError("action must be apply or dismiss", field="action")
    rows, truncated = _bulk_rows(session, body)
    if body.get("dry_run"):
        return {
            "dry_run": True,
            "matched": len(rows),
            "truncated": truncated,
            "decided": 0,
            "failed": 0,
            "failures": [],
        }
    decided = 0
    failures: list[dict[str, str]] = []
    for row in rows:
        try:
            with session.begin_nested():
                if action == "dismiss":
                    _mark(row, "dismissed", decided_by)
                else:
                    apply_proposal(session, row, translations=None)
                    _mark(row, "applied", decided_by)
            decided += 1
        except (ValidationError, NotFoundError, IntegrityError) as exc:
            message = (
                getattr(exc, "message", None) or "Could not apply the translation."
            )
            failures.append({"id": str(row.id), "message": message})
    session.flush()
    return {
        "dry_run": False,
        "matched": len(rows),
        "truncated": truncated,
        "decided": decided,
        "failed": len(failures),
        "failures": failures,
    }


def apply_proposal(
    session: Session,
    row: TranslationFixProposal,
    *,
    translations: dict[str, Any] | None,
) -> None:
    """Write proposed languages that are still empty. Leave stored text alone."""
    entity = _load_entity(session, row)
    gaps = entity_gaps(entity)
    gap = gaps.get(row.field)
    if gap is None:
        raise ValidationError("Those languages are already filled", field="field")
    if not _source_still_matches(dict(row.source_text or {}), gap["source"]):
        raise ValidationError("The source text changed. Sweep again.", field="field")
    proposed = _proposed_text(row, translations, gap["missing"], row.field)
    limit = MAX_NAME_LENGTH if row.field == "name" else MAX_DESCRIPTION_LENGTH
    written = False
    if "en" in gap["missing"]:
        english = text_value(proposed.get("en"))
        if english:
            if len(english) > limit:
                raise ValidationError(
                    f"{row.field} must be at most {limit} characters",
                    field=row.field,
                )
            _write_english(session, entity, row.field, english)
            written = True
    map_attr = (
        "name_translations" if row.field == "name" else "description_translations"
    )
    current_map = dict(getattr(entity, map_attr) or {})
    for lang in ("zh", "zh-HK"):
        if lang not in gap["missing"]:
            continue
        value = text_value(proposed.get(lang))
        if not value:
            continue
        if len(value) > limit:
            raise ValidationError(
                f"{row.field} must be at most {limit} characters",
                field=row.field,
            )
        if text_value(current_map.get(lang)):
            continue
        current_map[lang] = value
        written = True
    if not written:
        raise ValidationError("Nothing to translate", field="translations")
    setattr(entity, map_attr, current_map)
    session.flush()


def upsert_proposal(
    session: Session,
    *,
    entity_type: str,
    entity_id: str | UUID,
    org_id: str | UUID,
    field: str,
    source_text: dict[str, str],
    proposed_text: dict[str, str],
    missing_languages: list[str],
    confidence: Decimal | None = None,
    rationale: str | None = None,
    scan_run_id: str | UUID | None = None,
) -> str:
    """Insert or refresh one pending proposal. Returns created, updated, or skipped."""
    digest = source_hash(
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        source=source_text,
    )
    if _dismissed_hash(session, entity_type, entity_id, field, digest):
        clear_pending(session, entity_type, entity_id, field)
        return "skipped"
    now = datetime.now(timezone.utc)
    row = pending_row(session, entity_type, entity_id, field)
    if (
        row is not None
        and row.input_hash == digest
        and dict(row.proposed_text or {}) == proposed_text
    ):
        return "unchanged"
    if row is None:
        session.add(
            TranslationFixProposal(
                entity_type=entity_type,
                entity_id=entity_id,
                org_id=org_id,
                field=field,
                source_text=source_text,
                proposed_text=proposed_text,
                missing_languages=missing_languages,
                source="model",
                confidence=confidence,
                rationale=rationale,
                status="pending",
                scan_run_id=scan_run_id,
                input_hash=digest,
                created_at=now,
                updated_at=now,
            )
        )
        session.flush()
        return "created"
    row.source_text = source_text
    row.proposed_text = proposed_text
    row.missing_languages = missing_languages
    row.confidence = confidence
    row.rationale = rationale
    row.scan_run_id = None if scan_run_id is None else str(scan_run_id)
    row.input_hash = digest
    row.updated_at = now
    session.flush()
    return "updated"


def clear_pending(
    session: Session,
    entity_type: str,
    entity_id: str | UUID,
    field: str,
) -> bool:
    row = pending_row(session, entity_type, entity_id, field)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def _dismissed_hash(session, entity_type, entity_id, field, digest: str) -> bool:
    found = session.scalar(
        select(TranslationFixProposal.id).where(
            TranslationFixProposal.entity_type == entity_type,
            TranslationFixProposal.entity_id == entity_id,
            TranslationFixProposal.field == field,
            TranslationFixProposal.status == "dismissed",
            TranslationFixProposal.input_hash == digest,
        )
    )
    return found is not None


def _load_entity(
    session: Session, row: TranslationFixProposal
) -> Organization | Activity:
    entity: Organization | Activity | None
    if row.entity_type == "organization":
        entity = session.get(Organization, row.entity_id)
        table = "organizations"
    else:
        entity = session.get(Activity, row.entity_id)
        table = "activities"
    if entity is None:
        raise NotFoundError(table, str(row.entity_id))
    return entity


def _write_english(session: Session, entity, field: str, english: str) -> None:
    if field == "description":
        entity.description = english
        return
    if isinstance(entity, Organization):
        other = OrganizationRepository(session).find_by_name_case_insensitive(english)
        if other is not None and str(other.id) != str(entity.id):
            raise ValidationError(
                "This name matches another organization. Merge them from Duplicates.",
                field="name",
            )
        entity.name = english
        return
    clash = session.scalar(
        select(Activity.id).where(
            Activity.org_id == entity.org_id,
            Activity.id != entity.id,
            func.lower(func.trim(Activity.name)) == english.casefold(),
        )
    )
    if clash is not None:
        raise ValidationError(
            "This name matches another activity in the organization.",
            field="name",
        )
    entity.name = english


def _source_still_matches(stored: dict[str, Any], current: dict[str, Any]) -> bool:
    """True when every language the proposal was made from is unchanged."""
    for key, value in stored.items():
        if text_value(current.get(key)) != text_value(value):
            return False
    return True


def _proposed_text(
    row: TranslationFixProposal,
    translations: dict[str, Any] | None,
    missing: list[str],
    field: str,
) -> dict[str, str]:
    proposed = {
        key: text_value(value)
        for key, value in dict(row.proposed_text or {}).items()
        if key in LANGUAGES and text_value(value)
    }
    if translations is None:
        return proposed
    if not isinstance(translations, dict):
        raise ValidationError("translations must be an object", field="translations")
    for key, value in translations.items():
        if key not in LANGUAGES:
            raise ValidationError("Unknown language", field="translations")
        if key not in missing:
            continue
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValidationError("translations must be text", field="translations")
        cleaned = text_value(value)
        if cleaned:
            proposed[key] = cleaned
        else:
            proposed.pop(key, None)
    return proposed


def _mark(row: TranslationFixProposal, status: str, decided_by: str | None) -> None:
    now = datetime.now(timezone.utc)
    row.status = status
    row.decided_by = decided_by
    row.decided_at = now
    row.updated_at = now


def _bulk_rows(session: Session, body: dict[str, Any]):
    ids = body.get("ids")
    if isinstance(ids, list) and ids:
        parsed = []
        for raw in ids:
            try:
                parsed.append(UUID(str(raw)))
            except (TypeError, ValueError) as exc:
                raise ValidationError("ids must be UUIDs", field="ids") from exc
        rows = list(
            session.scalars(
                select(TranslationFixProposal).where(
                    TranslationFixProposal.id.in_(parsed),
                    TranslationFixProposal.status == "pending",
                )
            ).all()
        )
        return rows[:_MAX_BULK], len(rows) > _MAX_BULK
    entity_type = body.get("entity_type") or None
    field = body.get("field") or None
    if entity_type is not None and entity_type not in ENTITY_TYPES:
        raise ValidationError("Invalid entity_type", field="entity_type")
    if field is not None and field not in FIELDS:
        raise ValidationError("Invalid field", field="field")
    org_raw = body.get("org_id")
    org_id = None
    if org_raw:
        try:
            org_id = UUID(str(org_raw))
        except (TypeError, ValueError) as exc:
            raise ValidationError("org_id must be a UUID", field="org_id") from exc
    query = body.get("q")
    stmt = filtered_stmt(
        status="pending",
        entity_type=entity_type,
        field=field,
        org_id=org_id,
        query=query.strip() if isinstance(query, str) else None,
    )
    rows = list(session.scalars(stmt.limit(_MAX_BULK + 1)).all())
    return rows[:_MAX_BULK], len(rows) > _MAX_BULK
