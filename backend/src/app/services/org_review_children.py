"""Per-activity lookups that feed the organization review snapshot."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityLocation, Organization
from app.db.models.category_scan import ActivityCategoryReview


def added_since_rejected(
    organization: Organization,
    activities: list[Activity],
) -> bool:
    """True when a rejected organization gained an activity afterwards."""
    reviewed_at = organization.reviewed_at
    if (
        organization.review_status != "rejected"
        or not organization.review_reason
        or reviewed_at is None
    ):
        return False
    for activity in activities:
        created_at = getattr(activity, "created_at", None)
        if created_at is not None and created_at > reviewed_at:
            return True
    return False


def linked_activity_ids(session: Session, activity_ids: list) -> set[str]:
    """Activities that have at least one ``activity_locations`` row."""
    if not activity_ids:
        return set()
    rows = session.scalars(
        select(ActivityLocation.activity_id).where(
            ActivityLocation.activity_id.in_(activity_ids)
        )
    ).all()
    return {str(item) for item in rows}


def pending_category_check_ids(session: Session, activity_ids: list) -> set[str]:
    if not activity_ids:
        return set()
    rows = session.scalars(
        select(ActivityCategoryReview.activity_id).where(
            ActivityCategoryReview.activity_id.in_(activity_ids),
            ActivityCategoryReview.status == "pending",
        )
    ).all()
    return {str(item) for item in rows}


def counts_by_activity(
    session: Session,
    activity_id_column: Any,
    activity_ids: list[Any],
) -> dict[str, int]:
    if not activity_ids:
        return {}
    rows = session.execute(
        select(activity_id_column, func.count())
        .where(activity_id_column.in_(activity_ids))
        .group_by(activity_id_column)
    ).all()
    return {str(activity_id): cast(int, count) for activity_id, count in rows}
