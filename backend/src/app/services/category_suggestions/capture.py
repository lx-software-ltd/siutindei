"""Find-or-create a pending suggestion for an unknown category name."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    PENDING_CATEGORY_NAME,
    CategorySuggestion,
    CategorySuggestionActivity,
)
from app.db.repositories.category_suggestion import CategorySuggestionRepository
from app.services.category_suggestions.resolve import (
    current_batch,
    normalize_category_key,
    note_suggestion,
)

REENRICH_THRESHOLDS = (5, 25)


def record_import_capture(
    session: Session,
    activity: Activity,
    org: Organization,
    requested_name: str | None,
    import_job_id: UUID | None,
    warnings: list[str] | None,
) -> None:
    """Link a just-upserted activity when its category was captured."""
    if not requested_name:
        return
    job_id = import_job_id
    if isinstance(job_id, str):
        job_id = UUID(job_id)
    warning = capture_pending(
        session,
        activity=activity,
        requested_name=requested_name,
        org=org,
        import_job_id=job_id,
    )
    if warnings is not None:
        warnings.append(warning)


def capture_warning(name: str) -> str:
    """Row warning stored on the import result."""
    return f"category_name '{name}' captured as pending suggestion"


def ensure_pending_category(session: Session) -> ActivityCategory:
    """Insert the system category when the migration row is absent."""
    existing = session.get(ActivityCategory, PENDING_CATEGORY_ID)
    if existing is not None:
        return existing
    row = ActivityCategory(
        id=PENDING_CATEGORY_ID,
        name=PENDING_CATEGORY_NAME,
        name_translations={"zh": "待分類"},
        display_order=9999,
        parent_id=None,
    )
    session.add(row)
    session.flush()
    return row


def capture_pending(
    session: Session,
    *,
    activity: Activity,
    requested_name: str,
    org: Organization,
    import_job_id: UUID | None,
) -> str:
    """Link an activity to the pending suggestion for this name."""
    ensure_pending_category(session)
    fingerprint = normalize_category_key(requested_name) or requested_name.casefold()
    repo = CategorySuggestionRepository(session)
    suggestion = repo.get_by_fingerprint(fingerprint)
    reopened = False
    created = False
    now = datetime.now(timezone.utc)
    if suggestion is None:
        suggestion = CategorySuggestion(
            fingerprint=fingerprint,
            requested_name=requested_name.strip(),
            source="import",
            status="pending",
            enrichment_status="none",
        )
        session.add(suggestion)
        session.flush()
        created = True
    elif _is_reopenable(suggestion):
        suggestion.status = "pending"
        suggestion.reopened_at = now
        suggestion.enrichment_status = "none"
        suggestion.enrichment_error = None
        suggestion.updated_at = now
        reopened = True
    previous = int(suggestion.activity_count or 0)
    _replace_other_links(
        session,
        activity_id=UUID(str(activity.id)),
        keep=suggestion.id,
    )
    linked = _link_activity(
        session,
        suggestion=suggestion,
        activity=activity,
        org=org,
        import_job_id=import_job_id,
        requested_name=requested_name.strip(),
    )
    count = repo.refresh_activity_count(suggestion)
    should_enqueue = _should_enqueue(
        created=created,
        reopened=reopened,
        linked=linked,
        previous=previous,
        count=count,
    )
    note_suggestion(suggestion.id, enqueue=should_enqueue)
    return capture_warning(requested_name.strip())


def _is_reopenable(suggestion: CategorySuggestion) -> bool:
    return (
        suggestion.status == "rejected"
        and suggestion.created_category_id is None
        and suggestion.merged_into_category_id is None
    )


def _should_enqueue(
    *,
    created: bool,
    reopened: bool,
    linked: bool,
    previous: int,
    count: int,
) -> bool:
    batch = current_batch()
    if batch is not None and not batch.auto_enrich:
        return False
    if batch is None:
        return False
    if created or reopened:
        return True
    if not linked:
        return False
    return any(previous < threshold <= count for threshold in REENRICH_THRESHOLDS)


def _replace_other_links(
    session: Session,
    *,
    activity_id: UUID,
    keep: UUID,
) -> None:
    others = list(
        session.scalars(
            select(CategorySuggestionActivity.suggestion_id).where(
                CategorySuggestionActivity.activity_id == activity_id,
                CategorySuggestionActivity.suggestion_id != keep,
            )
        ).all()
    )
    if not others:
        return
    session.execute(
        delete(CategorySuggestionActivity).where(
            CategorySuggestionActivity.activity_id == activity_id,
            CategorySuggestionActivity.suggestion_id != keep,
        )
    )
    repo = CategorySuggestionRepository(session)
    for suggestion_id in others:
        row = session.get(CategorySuggestion, suggestion_id)
        if row is not None:
            repo.refresh_activity_count(row)


def _link_activity(
    session: Session,
    *,
    suggestion: CategorySuggestion,
    activity: Activity,
    org: Organization,
    import_job_id: UUID | None,
    requested_name: str,
) -> bool:
    existing = session.execute(
        select(CategorySuggestionActivity).where(
            CategorySuggestionActivity.suggestion_id == suggestion.id,
            CategorySuggestionActivity.activity_id == activity.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False
    session.add(
        CategorySuggestionActivity(
            suggestion_id=suggestion.id,
            activity_id=activity.id,
            org_id=org.id,
            import_job_id=import_job_id,
            requested_name=requested_name,
        )
    )
    session.flush()
    return True
