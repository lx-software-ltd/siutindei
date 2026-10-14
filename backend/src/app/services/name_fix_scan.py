"""Scan organization and activity names for cleanup proposals."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, Organization
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
    org_ids: list[UUID] | None = None,
    activity_ids: list[UUID] | None = None,
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
    explicit = org_ids is not None or activity_ids is not None
    if entity_type in (None, "organization") and (not explicit or org_ids is not None):
        for org in session.scalars(
            _org_stmt(org_id, query, review_scope, org_ids)
        ).all():
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
    if (
        entity_type in (None, "activity")
        and not truncated
        and (not explicit or activity_ids is not None)
    ):
        for activity in session.scalars(
            _activity_stmt(org_id, query, review_scope, activity_ids)
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


def _org_stmt(org_id, query, review_scope, org_ids=None):
    stmt = select(Organization).order_by(Organization.name, Organization.id)
    if org_ids is not None:
        return stmt.where(Organization.id.in_(org_ids or []))
    if org_id is not None:
        stmt = stmt.where(Organization.id == org_id)
    if query:
        stmt = stmt.where(Organization.name.ilike(ilike_pattern(query), escape="\\"))
    if review_scope == "pending_review":
        stmt = stmt.where(Organization.review_status == "pending_review")
    return stmt


def _activity_stmt(org_id, query, review_scope, activity_ids=None):
    stmt = (
        select(Activity)
        .join(Organization, Organization.id == Activity.org_id)
        .order_by(Activity.name, Activity.id)
    )
    if activity_ids is not None:
        return stmt.where(Activity.id.in_(activity_ids or []))
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
    from app.services.data_quality.names import upsert_name_proposal

    result = sanitize_name(current or "", translations or {}, config)
    return upsert_name_proposal(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        current=current or "",
        translations=translations or {},
        proposed=result.name,
        rules=list(result.rules),
        translation_patch=result.translation_patch or None,
        config=config,
        scan_run_id=run_id,
        status="pending",
    )


def _count(counts: dict[str, int], outcome: str) -> None:
    if outcome in counts:
        counts[outcome] += 1
