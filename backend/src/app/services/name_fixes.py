"""Store and apply name-cleanup proposals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.admin_validators import MAX_NAME_LENGTH
from app.db.models import Activity, NameFixProposal, NameFixSettings, Organization
from app.db.repositories import OrganizationRepository
from app.exceptions import NotFoundError, ValidationError
from app.services.name_sanitizer import (
    RULE_CODES,
    NameSanitizeConfig,
    sanitize_name,
)

_MAX_SCAN = 2000
_MAX_BULK = 200


def load_name_fix_config(session: Session) -> NameSanitizeConfig:
    """Return saved rule toggles, or the defaults when the row is missing."""
    row = session.get(NameFixSettings, 1)
    if row is None:
        return NameSanitizeConfig.defaults()
    enabled = {str(item) for item in row.enabled_rules or [] if str(item) in RULE_CODES}
    if not enabled:
        enabled = set(RULE_CODES)
    return NameSanitizeConfig(
        enabled_rules=frozenset(enabled),
        exception_words=frozenset(
            str(item).upper() for item in row.exception_words or []
        ),
        bracket_suffixes=frozenset(
            str(item).casefold() for item in row.bracket_suffixes or []
        ),
    )


def settings_payload(session: Session) -> dict[str, Any]:
    config = load_name_fix_config(session)
    return {
        "enabled_rules": [code for code in RULE_CODES if code in config.enabled_rules],
        "available_rules": list(RULE_CODES),
        "exception_words": sorted(config.exception_words),
        "bracket_suffixes": sorted(config.bracket_suffixes),
    }


def update_settings(session: Session, body: dict[str, Any]) -> dict[str, Any]:
    """Replace the singleton name-fix settings."""
    enabled = body.get("enabled_rules")
    words = body.get("exception_words")
    suffixes = body.get("bracket_suffixes")
    if (
        not isinstance(enabled, list)
        or not isinstance(words, list)
        or not isinstance(suffixes, list)
    ):
        raise ValidationError("Settings lists are required", field="enabled_rules")
    unknown = [item for item in enabled if item not in RULE_CODES]
    if unknown:
        raise ValidationError("Unknown rule", field="enabled_rules")
    clean_words = [_token(item, "exception_words", 20) for item in words]
    clean_suffixes = [
        _token(item, "bracket_suffixes", 40).casefold() for item in suffixes
    ]
    if len(clean_words) > 50 or len(clean_suffixes) > 30:
        raise ValidationError("Too many entries", field="exception_words")
    row = session.get(NameFixSettings, 1)
    if row is None:
        row = NameFixSettings(
            id=1, enabled_rules=[], exception_words=[], bracket_suffixes=[]
        )
        session.add(row)
    row.enabled_rules = [code for code in RULE_CODES if code in enabled]
    row.exception_words = clean_words
    row.bracket_suffixes = clean_suffixes
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return settings_payload(session)


def preview_name(
    session: Session, name: str, translations: dict | None
) -> dict[str, Any]:
    result = sanitize_name(name, translations or {}, load_name_fix_config(session))
    return {
        "name": result.name,
        "rules": list(result.rules),
        "translation_patch": result.translation_patch,
        "changed": result.changed,
    }


def scan_names(
    session: Session,
    *,
    entity_type: str | None = None,
    org_id: UUID | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Create or refresh pending proposals. Approved organizations' activities are skipped."""
    config = load_name_fix_config(session)
    run_id = uuid4()
    counts = {"created": 0, "updated": 0, "skipped": 0}
    seen = 0
    truncated = False
    if entity_type in (None, "organization"):
        org_stmt = select(Organization).order_by(Organization.name)
        if org_id is not None:
            org_stmt = org_stmt.where(Organization.id == org_id)
        if query:
            org_stmt = org_stmt.where(Organization.name.ilike(f"%{query}%"))
        for org in session.scalars(org_stmt).all():
            seen += 1
            if seen > _MAX_SCAN:
                truncated = True
                break
            _count(
                counts,
                _propose(
                    session,
                    "organization",
                    org.id,
                    org.name,
                    org.name_translations,
                    config,
                    run_id,
                ),
            )
    if entity_type in (None, "activity") and not truncated:
        activity_stmt = (
            select(Activity)
            .join(Organization, Organization.id == Activity.org_id)
            .where(Organization.review_status == "pending_review")
            .order_by(Activity.name)
        )
        if org_id is not None:
            activity_stmt = activity_stmt.where(Activity.org_id == org_id)
        if query:
            activity_stmt = activity_stmt.where(Activity.name.ilike(f"%{query}%"))
        for activity in session.scalars(activity_stmt).all():
            seen += 1
            if seen > _MAX_SCAN:
                truncated = True
                break
            _count(
                counts,
                _propose(
                    session,
                    "activity",
                    activity.id,
                    activity.name,
                    activity.name_translations,
                    config,
                    run_id,
                ),
            )
    session.flush()
    return {"scan_run_id": str(run_id), "truncated": truncated, **counts}


def list_proposals(
    session: Session,
    *,
    status: str | None,
    entity_type: str | None,
    rule: str | None,
    org_id: UUID | None,
    query: str | None,
    limit: int,
) -> dict[str, Any]:
    stmt = select(NameFixProposal).order_by(
        NameFixProposal.created_at.desc(), NameFixProposal.id
    )
    if status:
        stmt = stmt.where(NameFixProposal.status == status)
    if entity_type:
        stmt = stmt.where(NameFixProposal.entity_type == entity_type)
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                NameFixProposal.current_value.ilike(pattern),
                NameFixProposal.proposed_value.ilike(pattern),
            )
        )
    fetch_limit = 500 if rule or org_id is not None else limit + 1
    rows = list(session.scalars(stmt.limit(fetch_limit)).all())
    if rule:
        rows = [row for row in rows if rule in (row.rules or [])]
    if org_id is not None:
        rows = [row for row in rows if _proposal_org_id(session, row) == str(org_id)]
    page = rows[:limit]
    return {
        "items": [_serialize(row) for row in page],
        "next_cursor": None,
    }


def summarize_proposals(session: Session) -> dict[str, Any]:
    rows = session.execute(
        select(
            NameFixProposal.status, NameFixProposal.entity_type, func.count()
        ).group_by(
            NameFixProposal.status,
            NameFixProposal.entity_type,
        )
    ).all()
    by_status: dict[str, int] = {}
    by_entity: dict[str, int] = {}
    for status, entity_type, count in rows:
        by_status[status] = by_status.get(status, 0) + int(count)
        if status == "pending":
            by_entity[entity_type] = int(count)
    return {"by_status": by_status, "pending_by_entity": by_entity}


def decide_proposal(
    session: Session,
    proposal_id: UUID,
    action: str,
    value: str | None,
    decided_by: str | None,
) -> dict[str, Any]:
    row = session.get(NameFixProposal, proposal_id)
    if row is None:
        raise NotFoundError("name_fix_proposals", str(proposal_id))
    if row.status != "pending":
        raise ValidationError("Proposal is already decided", field="status")
    if action == "dismiss":
        _mark(row, "dismissed", decided_by)
        session.flush()
        return _serialize(row)
    if action != "apply":
        raise ValidationError("action must be apply or dismiss", field="action")
    proposed = (value if value is not None else row.proposed_value).strip()
    _apply_value(session, row, proposed)
    row.proposed_value = proposed
    _mark(row, "applied", decided_by)
    session.flush()
    return _serialize(row)


def decide_bulk(
    session: Session, body: dict[str, Any], decided_by: str | None
) -> dict[str, Any]:
    action = body.get("action")
    if action not in {"apply", "dismiss"}:
        raise ValidationError("action must be apply or dismiss", field="action")
    rows = _bulk_rows(session, body)
    if body.get("dry_run"):
        return {
            "dry_run": True,
            "matched": len(rows),
            "decided": 0,
            "failed": 0,
            "failures": [],
        }
    decided = 0
    failures = []
    for row in rows[:_MAX_BULK]:
        try:
            with session.begin_nested():
                if action == "dismiss":
                    _mark(row, "dismissed", decided_by)
                else:
                    _apply_value(session, row, row.proposed_value.strip())
                    row.proposed_value = row.proposed_value.strip()
                    _mark(row, "applied", decided_by)
            decided += 1
        except (ValidationError, NotFoundError) as exc:
            failures.append({"id": str(row.id), "message": exc.message})
    session.flush()
    return {
        "dry_run": False,
        "matched": len(rows),
        "decided": decided,
        "failed": len(failures),
        "failures": failures,
    }


def _bulk_rows(session: Session, body: dict[str, Any]) -> list[NameFixProposal]:
    ids = body.get("ids")
    stmt = select(NameFixProposal).where(NameFixProposal.status == "pending")
    if isinstance(ids, list) and ids:
        parsed = []
        for raw in ids:
            try:
                parsed.append(UUID(str(raw)))
            except ValueError as exc:
                raise ValidationError("id must be a UUID", field="ids") from exc
        stmt = stmt.where(NameFixProposal.id.in_(parsed))
    else:
        entity_type = body.get("entity_type")
        if entity_type:
            stmt = stmt.where(NameFixProposal.entity_type == entity_type)
        query = body.get("q")
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    NameFixProposal.current_value.ilike(pattern),
                    NameFixProposal.proposed_value.ilike(pattern),
                )
            )
    rows = list(session.scalars(stmt.limit(_MAX_BULK + 1)).all())
    rule = body.get("rule")
    if rule and not (isinstance(ids, list) and ids):
        rows = [row for row in rows if rule in (row.rules or [])]
    return rows


def _propose(
    session, entity_type, entity_id, current, translations, config, run_id
) -> str:
    result = sanitize_name(current or "", translations or {}, config)
    if not result.changed:
        return "unchanged"
    pending = session.scalars(
        select(NameFixProposal).where(
            NameFixProposal.entity_type == entity_type,
            NameFixProposal.entity_id == entity_id,
            NameFixProposal.field == "name",
            NameFixProposal.status == "pending",
        )
    ).first()
    if pending is not None:
        pending.current_value = current
        pending.proposed_value = result.name
        pending.rules = list(result.rules)
        pending.translation_patch = result.translation_patch or None
        pending.scan_run_id = run_id
        pending.updated_at = datetime.now(timezone.utc)
        return "updated"
    dismissed = session.scalars(
        select(NameFixProposal.id).where(
            NameFixProposal.entity_type == entity_type,
            NameFixProposal.entity_id == entity_id,
            NameFixProposal.status == "dismissed",
            NameFixProposal.proposed_value == result.name,
        )
    ).first()
    if dismissed is not None:
        return "skipped"
    session.add(
        NameFixProposal(
            entity_type=entity_type,
            entity_id=entity_id,
            current_value=current,
            proposed_value=result.name,
            rules=list(result.rules),
            translation_patch=result.translation_patch or None,
            scan_run_id=run_id,
        )
    )
    return "created"


def _apply_value(session: Session, row: NameFixProposal, proposed: str) -> None:
    if not proposed or len(proposed) > MAX_NAME_LENGTH:
        raise ValidationError("name length is invalid", field="name")
    if row.entity_type == "organization":
        org = session.get(Organization, row.entity_id)
        if org is None:
            raise NotFoundError("organizations", str(row.entity_id))
        other = OrganizationRepository(session).find_by_name_case_insensitive(proposed)
        if other is not None and str(other.id) != str(org.id):
            raise ValidationError(
                "This name matches another organization. Merge them from Duplicates.",
                field="name",
            )
        org.name = proposed
        _merge_patch(org, "name_translations", row.translation_patch)
        return
    activity = session.get(Activity, row.entity_id)
    if activity is None:
        raise NotFoundError("activities", str(row.entity_id))
    activity.name = proposed
    _merge_patch(activity, "name_translations", row.translation_patch)


def _merge_patch(entity, column: str, patch: dict | None) -> None:
    if not patch:
        return
    current = dict(getattr(entity, column) or {})
    for key, value in patch.items():
        if not str(current.get(key) or "").strip() and value:
            current[key] = value
    setattr(entity, column, current)


def _mark(row: NameFixProposal, status: str, decided_by: str | None) -> None:
    row.status = status
    row.decided_by = decided_by
    row.decided_at = datetime.now(timezone.utc)
    row.updated_at = row.decided_at


def _count(counts: dict[str, int], outcome: str) -> None:
    if outcome in counts:
        counts[outcome] += 1


def _proposal_org_id(session: Session, row: NameFixProposal) -> str | None:
    if row.entity_type == "organization":
        return str(row.entity_id)
    activity = session.get(Activity, row.entity_id)
    if activity is None:
        return None
    return str(activity.org_id)


def _serialize(row: NameFixProposal) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "entity_type": row.entity_type,
        "entity_id": str(row.entity_id),
        "current_value": row.current_value,
        "proposed_value": row.proposed_value,
        "rules": row.rules or [],
        "translation_patch": row.translation_patch,
        "status": row.status,
        "scan_run_id": str(row.scan_run_id) if row.scan_run_id else None,
        "decided_by": row.decided_by,
        "decided_at": row.decided_at,
        "created_at": row.created_at,
    }


def _token(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} entries must be strings", field=field)
    token = value.strip()
    if not token or len(token) > limit or any(char.isspace() for char in token):
        raise ValidationError(f"Invalid {field} entry", field=field)
    return token.upper() if field == "exception_words" else token
