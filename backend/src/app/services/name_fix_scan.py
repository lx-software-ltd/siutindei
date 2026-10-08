"""Scan organization and activity names for cleanup proposals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, NameFixProposal, Organization
from app.exceptions import ValidationError
from app.services.name_fix_query import ilike_pattern
from app.services.name_sanitizer import sanitize_name

_MAX_SWEEP = 10000
_REVIEW_SCOPES = frozenset({"pending_review", "all"})


def scan_names(
    session: Session,
    *,
    entity_type: str | None = None,
    org_id: UUID | None = None,
    query: str | None = None,
    review_scope: str,
) -> dict[str, Any]:
    """Sweep names and refresh pending proposals.

    ``review_scope`` is ``pending_review`` or ``all``. Pending rows the
    current rules no longer change are deleted.
    """
    if review_scope not in _REVIEW_SCOPES:
        raise ValidationError("Invalid review_scope", field="review_scope")
    from app.services.name_fixes import load_name_fix_config

    config = load_name_fix_config(session)
    run_id = uuid4()
    counts = {"created": 0, "updated": 0, "skipped": 0, "cleared": 0}
    seen = 0
    truncated = False
    if entity_type in (None, "organization"):
        for org in session.scalars(_org_stmt(org_id, query, review_scope)).all():
            seen += 1
            if seen > _MAX_SWEEP:
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
        for activity in session.scalars(
            _activity_stmt(org_id, query, review_scope)
        ).all():
            seen += 1
            if seen > _MAX_SWEEP:
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


def _org_stmt(org_id, query, review_scope):
    stmt = select(Organization).order_by(Organization.name)
    if org_id is not None:
        stmt = stmt.where(Organization.id == org_id)
    if query:
        stmt = stmt.where(Organization.name.ilike(ilike_pattern(query), escape="\\"))
    if review_scope == "pending_review":
        stmt = stmt.where(Organization.review_status == "pending_review")
    return stmt


def _activity_stmt(org_id, query, review_scope):
    stmt = (
        select(Activity)
        .join(Organization, Organization.id == Activity.org_id)
        .order_by(Activity.name)
    )
    if review_scope != "all":
        stmt = stmt.where(Organization.review_status == "pending_review")
    if org_id is not None:
        stmt = stmt.where(Activity.org_id == org_id)
    if query:
        stmt = stmt.where(Activity.name.ilike(ilike_pattern(query), escape="\\"))
    return stmt


def _propose(
    session,
    entity_type,
    entity_id,
    current,
    translations,
    config,
    run_id,
) -> str:
    result = sanitize_name(current or "", translations or {}, config)
    pending = session.scalars(
        select(NameFixProposal).where(
            NameFixProposal.entity_type == entity_type,
            NameFixProposal.entity_id == entity_id,
            NameFixProposal.field == "name",
            NameFixProposal.status == "pending",
        )
    ).first()
    if not result.changed:
        if pending is not None:
            session.delete(pending)
            return "cleared"
        return "unchanged"
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


def _count(counts: dict[str, int], outcome: str) -> None:
    if outcome in counts:
        counts[outcome] += 1
