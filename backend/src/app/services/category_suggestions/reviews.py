"""Admin decisions on category-check reviews."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityCategory
from app.db.models.category_scan import ActivityCategoryReview
from app.db.models.category_suggestion import PENDING_CATEGORY_ID, CategorySuggestion
from app.exceptions import ValidationError

_ACTIONS = {"apply", "dismiss", "revert"}
_OPEN = {"pending"}
_REVERTIBLE = {"auto_applied", "applied"}


def apply_review_decision(
    session: Session,
    review: ActivityCategoryReview,
    body: dict[str, Any],
    *,
    decided_by: str | None,
) -> ActivityCategoryReview:
    """Apply, dismiss, or revert one category-check review."""
    action = body.get("action")
    if action not in _ACTIONS:
        raise ValidationError(
            "action must be apply, dismiss, or revert",
            field="action",
        )
    if action == "revert":
        decided = _revert(session, review, decided_by)
    elif review.status not in _OPEN:
        raise ValidationError("Review is already decided", field="status")
    elif action == "dismiss":
        decided = _decide(review, "dismissed", decided_by)
    else:
        decided = _apply(session, review, body, decided_by)
    session.flush()
    return decided


def apply_suggestion_to_reviews(
    session: Session,
    suggestion: CategorySuggestion,
    *,
    target_id: UUID | None,
    decided_by: str | None,
) -> None:
    """Move or dismiss reviews that are waiting on this suggestion."""
    reviews = list(
        session.scalars(
            select(ActivityCategoryReview).where(
                ActivityCategoryReview.suggestion_id == suggestion.id,
                ActivityCategoryReview.status == "pending",
            )
        ).all()
    )
    now = datetime.now(timezone.utc)
    for review in reviews:
        activity = session.get(Activity, review.activity_id)
        if target_id is not None and activity is not None:
            review.previous_category_id = _uuid(activity.category_id)
            activity.category_id = target_id  # type: ignore[assignment]
            review.proposed_category_id = target_id
            review.status = "applied"
        else:
            review.status = "dismissed"
        review.decided_by = decided_by
        review.decided_at = now


def _apply(
    session: Session,
    review: ActivityCategoryReview,
    body: dict[str, Any],
    decided_by: str | None,
) -> ActivityCategoryReview:
    activity = session.get(Activity, review.activity_id)
    if activity is None:
        raise ValidationError("Activity no longer exists", field="activity_id")
    target = _target(session, body.get("category_id")) or _target(
        session, review.proposed_category_id
    )
    if target is None:
        if (
            review.verdict == "confirm"
            and _uuid(activity.category_id) != PENDING_CATEGORY_ID
        ):
            return _decide(review, "confirmed", decided_by)
        raise ValidationError("category_id is required", field="category_id")
    review.previous_category_id = _uuid(activity.category_id)
    activity.category_id = target.id  # type: ignore[assignment]
    review.proposed_category_id = _uuid(target.id)
    return _decide(review, "applied", decided_by)


def _revert(
    session: Session,
    review: ActivityCategoryReview,
    decided_by: str | None,
) -> ActivityCategoryReview:
    if review.status not in _REVERTIBLE:
        raise ValidationError(
            "Only an applied category can be reverted", field="status"
        )
    if review.previous_category_id is None:
        raise ValidationError("Previous category is missing", field="category_id")
    activity = session.get(Activity, review.activity_id)
    if activity is None:
        raise ValidationError("Activity no longer exists", field="activity_id")
    previous = session.get(ActivityCategory, review.previous_category_id)
    if previous is None or _uuid(previous.id) == PENDING_CATEGORY_ID:
        raise ValidationError("Previous category is missing", field="category_id")
    activity.category_id = previous.id  # type: ignore[assignment]
    return _decide(review, "reverted", decided_by)


def _decide(
    review: ActivityCategoryReview,
    status: str,
    decided_by: str | None,
) -> ActivityCategoryReview:
    review.status = status
    review.decided_by = decided_by
    review.decided_at = datetime.now(timezone.utc)
    return review


def _target(session: Session, raw: Any) -> ActivityCategory | None:
    category_id = _uuid(raw)
    if category_id is None:
        return None
    if category_id == PENDING_CATEGORY_ID:
        raise ValidationError(
            "Pending categorisation cannot be a decision target",
            field="category_id",
        )
    category = session.get(ActivityCategory, category_id)
    if category is None:
        raise ValidationError("category_id not found", field="category_id")
    return category


def _uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Invalid category_id", field="category_id") from exc
