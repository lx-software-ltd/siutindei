"""Name proposals shared by the sweep and by import."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NameFixProposal
from app.services.data_quality.fingerprint import fingerprint
from app.services.name_sanitizer import NameSanitizeConfig

NAME_CHECK_VERSION = "names-1"


def name_input_hash(
    *,
    entity_type: str,
    current: str,
    translations: dict[str, Any] | None,
    proposed: str,
    rules: list[str],
    translation_patch: dict[str, Any] | None,
    config: NameSanitizeConfig,
) -> str:
    """Hash the inputs that decide one name proposal."""
    return fingerprint(
        {
            "version": NAME_CHECK_VERSION,
            "entity_type": entity_type,
            "current": current or "",
            "translations": _map(translations),
            "proposed": proposed,
            "rules": sorted(rules),
            "translation_patch": _map(translation_patch),
            "config": {
                "enabled_rules": sorted(config.enabled_rules),
                "exception_words": sorted(config.exception_words),
                "bracket_suffixes": sorted(config.bracket_suffixes),
            },
        }
    )


def upsert_name_proposal(
    session: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    current: str,
    translations: dict[str, Any] | None,
    proposed: str,
    rules: list[str],
    translation_patch: dict[str, Any] | None,
    config: NameSanitizeConfig,
    scan_run_id: UUID | None,
    status: str,
    decided_by: str | None = None,
) -> str:
    """Insert or refresh one name proposal. A matching hash writes nothing."""
    patch = translation_patch or None
    changed = proposed != (current or "") or bool(patch)
    pending = _pending(session, entity_type, entity_id)
    if not changed:
        if pending is not None:
            session.delete(pending)
            return "cleared"
        return "unchanged"
    digest = name_input_hash(
        entity_type=entity_type,
        current=current or "",
        translations=translations,
        proposed=proposed,
        rules=rules,
        translation_patch=patch,
        config=config,
    )
    if (
        status == "pending"
        and pending is None
        and _dismissed(session, entity_type, entity_id, proposed)
    ):
        return "skipped"
    if pending is not None:
        if (
            pending.input_hash == digest
            and pending.proposed_value == proposed
            and pending.status == "pending"
            and status == "pending"
        ):
            return "unchanged"
        _fill(pending, current, proposed, rules, patch, scan_run_id, digest)
        if status == "applied":
            _mark_applied(pending, decided_by)
            return "applied"
        pending.updated_at = datetime.now(timezone.utc)
        return "updated"
    if status == "applied" and _applied_same(session, entity_type, entity_id, digest):
        return "unchanged"
    now = datetime.now(timezone.utc)
    applied = status == "applied"
    session.add(
        NameFixProposal(
            entity_type=entity_type,
            entity_id=entity_id,
            current_value=current or "",
            proposed_value=proposed,
            rules=list(rules),
            translation_patch=patch,
            scan_run_id=scan_run_id,
            input_hash=digest,
            status="applied" if applied else "pending",
            decided_by=decided_by if applied else None,
            decided_at=now if applied else None,
        )
    )
    return "applied" if applied else "created"


def record_imported_name(
    session: Session,
    entity: Any,
    body: dict[str, Any],
    entity_type: str,
) -> None:
    """Write the proposal stashed by the import, then drop the stash.

    A client-supplied ``_name_change`` is discarded. Only the token
    written by name preparation can record a proposal.
    """
    body.pop("_name_change", None)
    token = body.pop("_import_name_token", None)
    change = session.info.pop(id(token), None) if token is not None else None
    if not isinstance(change, dict):
        return
    if getattr(entity, "id", None) is None:
        entity.id = uuid4()
    from app.services.name_fixes import load_name_fix_config

    config = load_name_fix_config(session)
    raw_rules = change.get("rules")
    rules = raw_rules if isinstance(raw_rules, list) else []
    patch = change.get("translation_patch")
    upsert_name_proposal(
        session,
        entity_type=entity_type,
        entity_id=entity.id,
        current=str(change.get("original") or ""),
        translations=change.get("translations")
        if isinstance(change.get("translations"), dict)
        else None,
        proposed=str(change.get("proposed") or ""),
        rules=[str(item) for item in rules],
        translation_patch=patch if isinstance(patch, dict) else None,
        config=config,
        scan_run_id=None,
        status=str(change.get("status") or "pending"),
        decided_by="import" if change.get("status") == "applied" else None,
    )


def _pending(
    session: Session, entity_type: str, entity_id: UUID
) -> NameFixProposal | None:
    return session.scalars(
        select(NameFixProposal).where(
            NameFixProposal.entity_type == entity_type,
            NameFixProposal.entity_id == entity_id,
            NameFixProposal.field == "name",
            NameFixProposal.status == "pending",
        )
    ).first()


def _dismissed(
    session: Session, entity_type: str, entity_id: UUID, proposed: str
) -> bool:
    found = session.scalars(
        select(NameFixProposal.id).where(
            NameFixProposal.entity_type == entity_type,
            NameFixProposal.entity_id == entity_id,
            NameFixProposal.status == "dismissed",
            NameFixProposal.proposed_value == proposed,
        )
    ).first()
    return found is not None


def _applied_same(
    session: Session, entity_type: str, entity_id: UUID, digest: str
) -> bool:
    found = session.scalars(
        select(NameFixProposal.id).where(
            NameFixProposal.entity_type == entity_type,
            NameFixProposal.entity_id == entity_id,
            NameFixProposal.status == "applied",
            NameFixProposal.input_hash == digest,
        )
    ).first()
    return found is not None


def _fill(row, current, proposed, rules, patch, scan_run_id, digest) -> None:
    row.current_value = current or ""
    row.proposed_value = proposed
    row.rules = list(rules)
    row.translation_patch = patch
    row.scan_run_id = scan_run_id
    row.input_hash = digest


def _mark_applied(row: NameFixProposal, decided_by: str | None) -> None:
    now = datetime.now(timezone.utc)
    row.status = "applied"
    row.decided_by = decided_by
    row.decided_at = now
    row.updated_at = now


def _map(value: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}
