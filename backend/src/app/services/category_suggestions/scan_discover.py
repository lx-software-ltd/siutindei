"""Group imported category labels and ask about ones not in the taxonomy."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from datetime import timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_scan import ActivityCategoryReview, CategoryScanRun
from app.db.models.category_suggestion import CategorySuggestion
from app.db.repositories.category_suggestion import CategorySuggestionRepository
from app.services.category_suggestions.capture import (
    REENRICH_THRESHOLDS,
    _is_reopenable,
    _link_activity,
    _replace_other_links,
)
from app.services.category_suggestions.resolve import (
    matching_category_id,
    normalize_category_key,
)
from app.services.category_suggestions.scan import CategoryScanBusy, _chunks
from app.services.category_suggestions.scan_apply import _add_review, _overridden


def count_discover(
    session: Session,
    *,
    org_id: UUID | None = None,
) -> tuple[int, int]:
    """Uncapped activity count and unknown labels a discover run would model."""
    groups = _groups(session, org_id=org_id)
    activities = sum(len(rows) for rows in groups.values())
    labels = sum(
        1 for key, rows in groups.items() if _label_needs_model(session, key, rows)
    )
    return activities, labels


def start_discover(
    session: Session,
    *,
    requested_by: str | None,
    org_id: UUID | None,
    limit: int,
    batch_size: int,
    rescan: bool,
) -> tuple[CategoryScanRun, list[list[str]]]:
    """Assign known labels now and queue unknown labels for the model."""
    groups = _groups(session, org_id=org_id)
    known, unknown = _split(session, groups)
    unknown_keys = sorted(unknown)[:limit]
    seen_ids: set[str] = set()
    for key in list(known) + unknown_keys:
        for activity in groups[key]:
            seen_ids.add(str(activity.id))
    suggestion_ids: list[str] = []
    for key in unknown_keys:
        suggestion_id = _capture_label(
            session,
            key,
            groups[key],
            rescan=rescan,
        )
        if suggestion_id is not None:
            suggestion_ids.append(suggestion_id)
    now = datetime.now(timezone.utc)
    batches = _chunks(suggestion_ids, batch_size)
    run = CategoryScanRun(
        status="done" if not batches else "queued",
        requested_by=requested_by,
        org_id=org_id,
        mode="discover",
        batch_size=batch_size,
        total_activities=len(seen_ids),
        labels_total=len(unknown_keys),
        batches_total=len(batches),
        finished_at=now if not batches else None,
        updated_at=now,
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise CategoryScanBusy() from exc
    _attach_known_reviews(session, run, known, groups, now)
    session.flush()
    return run, batches


def _groups(
    session: Session,
    *,
    org_id: UUID | None,
) -> dict[str, list[Activity]]:
    pending = (
        select(ActivityCategoryReview.id)
        .where(ActivityCategoryReview.activity_id == Activity.id)
        .where(ActivityCategoryReview.status == "pending")
    )
    query = (
        select(Activity)
        .join(Organization, Organization.id == Activity.org_id)
        .where(Organization.review_status == "pending_review")
        .where(Activity.source_category_name.is_not(None))
        .where(~pending.exists())
    )
    if org_id is not None:
        query = query.where(Activity.org_id == org_id)
    grouped: dict[str, list[Activity]] = defaultdict(list)
    for activity in session.scalars(query).all():
        raw = (activity.source_category_name or "").strip()
        if not raw:
            continue
        key = normalize_category_key(raw) or raw.casefold()
        grouped[key].append(activity)
    return grouped


def _split(
    session: Session,
    groups: dict[str, list[Activity]],
) -> tuple[dict[str, UUID], dict[str, list[Activity]]]:
    known: dict[str, UUID] = {}
    unknown: dict[str, list[Activity]] = {}
    for key, rows in groups.items():
        target = _known_target(session, key, rows)
        if target is None:
            unknown[key] = rows
        else:
            known[key] = target
    return known, unknown


def _known_target(
    session: Session,
    key: str,
    rows: list[Activity],
) -> UUID | None:
    name = _preferred_name([row.source_category_name or "" for row in rows])
    matched = matching_category_id(session, name)
    if matched is not None:
        return matched
    suggestion = CategorySuggestionRepository(session).get_by_fingerprint(key)
    if suggestion is None:
        return None
    if suggestion.status == "approved" and suggestion.created_category_id:
        return UUID(str(suggestion.created_category_id))
    if suggestion.status == "merged" and suggestion.merged_into_category_id:
        return UUID(str(suggestion.merged_into_category_id))
    return None


def _label_needs_model(
    session: Session,
    key: str,
    rows: list[Activity],
) -> bool:
    if _known_target(session, key, rows) is not None:
        return False
    suggestion = CategorySuggestionRepository(session).get_by_fingerprint(key)
    if suggestion is None or _is_reopenable(suggestion):
        return True
    if suggestion.status != "pending":
        return False
    return suggestion.enrichment_status in {"none", "failed"}


def _attach_known_reviews(
    session: Session,
    run: CategoryScanRun,
    known: dict[str, UUID],
    groups: dict[str, list[Activity]],
    now: datetime,
) -> None:
    overridden = _overridden(
        session,
        [str(row.id) for key in known for row in groups[key]],
    )
    for key, target_id in known.items():
        target = session.get(ActivityCategory, target_id)
        if target is None:
            continue
        for activity in groups[key]:
            _move_known(
                session,
                run,
                activity,
                target,
                overridden=str(activity.id) in overridden,
                now=now,
            )


def _move_known(
    session: Session,
    run: CategoryScanRun,
    activity: Activity,
    target: ActivityCategory,
    *,
    overridden: bool,
    now: datetime,
) -> None:
    org = session.get(Organization, activity.org_id)
    if org is None or org.review_status != "pending_review":
        return
    if str(activity.category_id) == str(target.id):
        return
    previous = UUID(str(activity.category_id))
    can_auto = not overridden
    if can_auto:
        activity.category_id = target.id  # type: ignore[assignment]
    _add_review(
        session,
        run=run,
        activity=activity,
        verdict="reassign",
        status="auto_applied" if can_auto else "pending",
        confidence=1,
        rationale="Imported label matches an existing category",
        now=now,
        proposed_category_id=UUID(str(target.id)),
        previous_category_id=previous if can_auto else None,
        decided_by=f"category-scan:{run.id}" if can_auto else None,
    )
    if can_auto:
        run.auto_applied = int(run.auto_applied or 0) + 1
    else:
        run.reassign_pending = int(run.reassign_pending or 0) + 1


def _capture_label(
    session: Session,
    key: str,
    rows: list[Activity],
    *,
    rescan: bool,
) -> str | None:
    repo = CategorySuggestionRepository(session)
    suggestion = repo.get_by_fingerprint(key)
    now = datetime.now(timezone.utc)
    created = False
    if suggestion is None:
        suggestion = CategorySuggestion(
            fingerprint=key,
            requested_name=_preferred_name(
                [row.source_category_name or "" for row in rows]
            ),
            source="scan",
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
    elif suggestion.status != "pending":
        return None
    previous = int(suggestion.activity_count or 0)
    linked = False
    for activity in rows:
        org = session.get(Organization, activity.org_id)
        if org is None:
            continue
        _replace_other_links(
            session,
            activity_id=UUID(str(activity.id)),
            keep=suggestion.id,
        )
        linked = (
            _link_activity(
                session,
                suggestion=suggestion,
                activity=activity,
                org=org,
                import_job_id=None,
                requested_name=(activity.source_category_name or "").strip(),
            )
            or linked
        )
    count = repo.refresh_activity_count(suggestion)
    if not _enqueue_model(
        suggestion,
        rescan=rescan,
        created=created,
        linked=linked,
        previous=previous,
        count=count,
    ):
        return None
    return str(suggestion.id)


def _enqueue_model(
    suggestion: CategorySuggestion,
    *,
    rescan: bool,
    created: bool,
    linked: bool,
    previous: int,
    count: int,
) -> bool:
    if suggestion.status != "pending":
        return False
    if rescan or created or suggestion.enrichment_status in {"none", "failed"}:
        return True
    if not linked:
        return False
    return any(previous < threshold <= count for threshold in REENRICH_THRESHOLDS)


def _preferred_name(names: list[str]) -> str:
    counts: dict[str, int] = {}
    for name in names:
        text = name.strip()
        if text:
            counts[text] = counts.get(text, 0) + 1
    if not counts:
        return ""
    return min(counts, key=lambda name: (-counts[name], len(name), name.casefold()))
