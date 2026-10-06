"""Admin decisions on category-check reviews."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_scan import ActivityCategoryReview
from app.db.models.category_suggestion import PENDING_CATEGORY_ID, CategorySuggestion
from app.exceptions import ValidationError

_BULK_ACTIONS = {"apply", "dismiss"}
BULK_PAGE_SIZE = 100
_FAILURE_LIMIT = 20

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


def decide_matching_reviews(
    session: Session,
    body: dict[str, Any],
    *,
    decided_by: str | None,
    cursor: tuple[datetime, UUID] | None,
) -> dict[str, Any]:
    """Apply or dismiss one page of pending reviews that match filters.

    ``dry_run`` counts the full match and writes nothing. A page walks
    ``created_at`` backwards, including rows that are skipped, so a
    block of reviews that cannot be applied does not hide later pages.
    """
    action = body.get("action")
    if action not in _BULK_ACTIONS:
        raise ValidationError(
            "action must be apply or dismiss",
            field="action",
        )
    dry_run = body.get("dry_run", False)
    if not isinstance(dry_run, bool):
        raise ValidationError("dry_run must be a boolean", field="dry_run")
    filters = _bulk_filters(body)
    matched, applicable = _count_pending(session, filters)
    if dry_run:
        skipped = matched - applicable if action == "apply" else 0
        return {
            "decided": 0,
            "skipped": skipped,
            "failed": 0,
            "failures": [],
            "matched": matched,
            "applicable": applicable if action == "apply" else matched,
            "next_cursor": None,
        }
    rows = list(
        session.scalars(
            _pending_stmt(filters, cursor=cursor).limit(BULK_PAGE_SIZE + 1)
        ).all()
    )
    page = rows[:BULK_PAGE_SIZE]
    has_more = len(rows) > BULK_PAGE_SIZE
    decided = 0
    skipped = 0
    failed = 0
    failures: list[dict[str, str]] = []
    for review in page:
        if action == "apply" and not _can_bulk_apply(review):
            skipped += 1
            continue
        try:
            with session.begin_nested():
                apply_review_decision(
                    session,
                    review,
                    {"action": action},
                    decided_by=decided_by,
                )
            decided += 1
        except ValidationError as exc:
            failed += 1
            if len(failures) < _FAILURE_LIMIT:
                failures.append({"id": str(review.id), "message": exc.message})
    last = page[-1] if page and has_more else None
    return {
        "decided": decided,
        "skipped": skipped,
        "failed": failed,
        "failures": failures,
        "matched": matched,
        "applicable": applicable if action == "apply" else matched,
        "next_review": last,
    }


def _bulk_filters(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": _choice(body.get("verdict"), {"confirm", "reassign", "propose"}),
        "org_id": _optional_uuid(body.get("org_id"), "org_id"),
        "scan_run_id": _optional_uuid(body.get("scan_run_id"), "scan_run_id"),
        "proposed_category_id": _optional_uuid(
            body.get("proposed_category_id"),
            "proposed_category_id",
        ),
        "query_text": str(body.get("q") or "").strip(),
    }


def _choice(value: Any, allowed: set[str]) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or value not in allowed:
        raise ValidationError("Invalid verdict", field="verdict")
    return value


def _optional_uuid(value: Any, field: str) -> UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid {field}", field=field) from exc


def _count_pending(session: Session, filters: dict[str, Any]) -> tuple[int, int]:
    matched = int(
        session.scalar(
            select(func.count()).select_from(_pending_stmt(filters).subquery())
        )
        or 0
    )
    applicable = int(
        session.scalar(
            select(func.count()).select_from(
                _pending_stmt(filters).where(_applicable()).subquery()
            )
        )
        or 0
    )
    return matched, applicable


def _pending_stmt(
    filters: dict[str, Any],
    *,
    cursor: tuple[datetime, UUID] | None = None,
):
    query = select(ActivityCategoryReview).where(
        ActivityCategoryReview.status == "pending"
    )
    if filters["verdict"]:
        query = query.where(ActivityCategoryReview.verdict == filters["verdict"])
    if filters["org_id"] is not None:
        query = query.where(ActivityCategoryReview.org_id == filters["org_id"])
    if filters["scan_run_id"] is not None:
        query = query.where(
            ActivityCategoryReview.scan_run_id == filters["scan_run_id"]
        )
    if filters["proposed_category_id"] is not None:
        query = query.where(
            ActivityCategoryReview.proposed_category_id
            == filters["proposed_category_id"]
        )
    if filters["query_text"]:
        like = _like(filters["query_text"])
        query = query.join(
            Activity, Activity.id == ActivityCategoryReview.activity_id
        ).join(Organization, Organization.id == ActivityCategoryReview.org_id)
        query = query.where(
            or_(
                func.lower(Activity.name).like(like, escape="\\"),
                func.lower(Organization.name).like(like, escape="\\"),
            )
        )
    if cursor is not None:
        created_at, review_id = cursor
        query = query.where(
            or_(
                ActivityCategoryReview.created_at < created_at,
                and_(
                    ActivityCategoryReview.created_at == created_at,
                    ActivityCategoryReview.id < review_id,
                ),
            )
        )
    return query.order_by(
        ActivityCategoryReview.created_at.desc(),
        ActivityCategoryReview.id.desc(),
    )


def _applicable():
    return or_(
        ActivityCategoryReview.proposed_category_id.is_not(None),
        and_(
            ActivityCategoryReview.verdict == "confirm",
            ActivityCategoryReview.current_category_id.is_not(None),
            ActivityCategoryReview.current_category_id != PENDING_CATEGORY_ID,
        ),
    )


def _can_bulk_apply(review: ActivityCategoryReview) -> bool:
    if review.proposed_category_id is not None:
        return True
    return (
        review.verdict == "confirm"
        and review.current_category_id is not None
        and review.current_category_id != PENDING_CATEGORY_ID
    )


def _like(value: str) -> str:
    escaped = (
        value.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


def _uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Invalid category_id", field="category_id") from exc
