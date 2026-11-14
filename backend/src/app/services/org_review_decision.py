"""Record a review decision on an organization."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.category_visibility import public_category_clause
from app.db.models import Activity, Organization
from app.utils.logging import get_logger

logger = get_logger(__name__)

HIDDEN_CATEGORY_REVIEWER = "system:category"
HIDDEN_ONLY_IMPORT_WARNING = (
    "every activity is in a category hidden from public search; "
    "organization rejected as not relevant"
)


def set_review_decision(
    organization: Organization,
    action: str,
    *,
    reviewer: str | None,
    reason: str | None = None,
) -> None:
    """Set review status, reason, and who decided when. Checks run first."""
    if action == "approve":
        organization.review_status = "approved"
        organization.review_reason = None
    elif action == "reject":
        organization.review_status = "rejected"
        organization.review_reason = reason
    else:
        organization.review_status = "pending_review"
        organization.review_reason = None
    organization.reviewed_at = datetime.now(UTC)
    organization.reviewed_by = reviewer


def reject_if_only_hidden(session: Session, organization_id: UUID | str) -> bool:
    """Reject as not relevant when every activity is in a hidden category.

    An organization with no activities, or one already rejected, is left
    alone. Moving an activity out of a hidden category later does not
    undo the rejection.
    """
    session.flush()
    organization = session.get(Organization, organization_id)
    if organization is None or organization.review_status == "rejected":
        return False
    total, listable = session.execute(
        select(
            func.count(Activity.id),
            func.count(Activity.id).filter(
                public_category_clause(Activity.category_id)
            ),
        ).where(Activity.org_id == organization.id)
    ).one()
    if not total or listable:
        return False
    set_review_decision(
        organization,
        "reject",
        reviewer=HIDDEN_CATEGORY_REVIEWER,
        reason="not_relevant",
    )
    session.flush()
    logger.info(
        "Organization rejected: every activity is in a hidden category",
        extra={"org_id": str(organization.id)},
    )
    return True
