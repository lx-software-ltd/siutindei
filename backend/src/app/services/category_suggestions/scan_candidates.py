"""Which activities a category check will read."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Activity, Organization
from app.db.models.category_scan import ActivityCategoryReview

DEFAULT_LIMIT = 500


def select_candidate_ids(
    session: Session,
    *,
    org_id: UUID | None = None,
    limit: int = DEFAULT_LIMIT,
    rescan: bool = False,
    review_scope: str = "pending_review",
) -> list[UUID]:
    """Activities that still need a check in ``review_scope``."""
    query = _candidate_stmt(org_id=org_id, rescan=rescan, review_scope=review_scope)
    rows = session.scalars(
        query.order_by(Activity.created_at, Activity.id).limit(limit)
    ).all()
    return [UUID(str(item)) for item in rows]


def count_candidates(
    session: Session,
    *,
    org_id: UUID | None = None,
    rescan: bool = False,
    review_scope: str = "pending_review",
) -> int:
    """How many activities a scan would see, without the per-run cap."""
    stmt = _candidate_stmt(
        org_id=org_id, rescan=rescan, review_scope=review_scope
    ).subquery()
    return int(session.scalar(select(func.count()).select_from(stmt)) or 0)


def resolve_scan_ids(
    session: Session,
    *,
    org_id: UUID | None,
    limit: int,
    rescan: bool,
    review_scope: str,
    activity_ids: list | None = None,
) -> list[UUID]:
    """Explicit ids skip the 30-day window. Otherwise use the normal filter."""
    if activity_ids is None:
        return select_candidate_ids(
            session,
            org_id=org_id,
            limit=limit,
            rescan=rescan,
            review_scope=review_scope,
        )
    parsed: list[UUID] = []
    for raw in activity_ids:
        try:
            parsed.append(UUID(str(raw)))
        except (TypeError, ValueError):
            continue
    if not parsed:
        return []
    rows = session.scalars(
        select(Activity.id)
        .where(Activity.id.in_(parsed))
        .order_by(Activity.created_at, Activity.id)
        .limit(limit)
    ).all()
    return [UUID(str(item)) for item in rows]


def _candidate_stmt(*, org_id: UUID | None, rescan: bool, review_scope: str):
    """Activities with no open review, limited by ``review_scope``."""
    from app.services.category_suggestions.scan import SKIP_WINDOW, _SETTLED

    query = select(Activity.id).join(Organization, Organization.id == Activity.org_id)
    if review_scope != "all":
        query = query.where(Organization.review_status == "pending_review")
    if org_id is not None:
        query = query.where(Activity.org_id == org_id)
    pending = (
        select(ActivityCategoryReview.id)
        .where(ActivityCategoryReview.activity_id == Activity.id)
        .where(ActivityCategoryReview.status == "pending")
    )
    query = query.where(~pending.exists())
    if not rescan:
        cutoff = datetime.now(timezone.utc) - SKIP_WINDOW
        settled = (
            select(ActivityCategoryReview.id)
            .where(ActivityCategoryReview.activity_id == Activity.id)
            .where(ActivityCategoryReview.status.in_(_SETTLED))
            .where(ActivityCategoryReview.created_at >= cutoff)
        )
        query = query.where(~settled.exists())
    return query
