"""Group imported category labels and ask about ones not in the taxonomy."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_scan import ActivityCategoryReview, CategoryScanRun
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    CategorySuggestion,
)
from app.db.repositories.category_suggestion import CategorySuggestionRepository
from app.services.category_suggestions.capture import (
    REENRICH_THRESHOLDS,
    _link_activity,
    _replace_other_links,
)
from app.services.category_suggestions.resolve import normalize_category_key
from app.services.category_suggestions.scan import CategoryScanBusy, _chunks
from app.services.category_suggestions.scan_apply import (
    _add_review,
    _audit_scan,
)

# An admin already decided, or verify already settled the category.
_LEAVE = ("applied", "confirmed", "dismissed", "reverted")


@dataclass
class _Catalog:
    """Taxonomy and suggestions loaded once for a discover pass."""

    exact: dict[str, list[UUID]]
    by_key: dict[str, set[UUID]]
    live_ids: set[UUID]
    suggestions: dict[str, CategorySuggestion]


def count_discover(
    session: Session,
    *,
    org_id: UUID | None = None,
) -> tuple[int, int]:
    """Pending activities and labels a default discover run would model."""
    groups = _groups(session, org_id=org_id)
    catalog = _catalog(session, list(groups))
    activities = sum(len(rows) for rows in groups.values())
    labels = sum(
        1
        for key, rows in groups.items()
        if _preview_enqueue(catalog, key, rows, rescan=False)
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
    now = datetime.now(timezone.utc)
    run = CategoryScanRun(
        status="running",
        requested_by=requested_by,
        org_id=org_id,
        mode="discover",
        batch_size=batch_size,
        total_activities=0,
        labels_total=0,
        batches_total=0,
        updated_at=now,
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise CategoryScanBusy() from exc
    groups = _groups(session, org_id=org_id)
    catalog = _catalog(session, list(groups))
    orgs = _orgs(session, groups)
    known, unknown = _split(catalog, groups)
    model_keys = [
        key
        for key in sorted(unknown)
        if _preview_enqueue(catalog, key, groups[key], rescan=rescan)
    ]
    chosen = set(model_keys[:limit])
    suggestion_ids: list[str] = []
    for key in sorted(unknown):
        suggestion_id = _capture_label(
            session,
            catalog,
            orgs,
            key,
            groups[key],
            rescan=rescan,
            allow_enqueue=key in chosen,
        )
        if suggestion_id is not None:
            suggestion_ids.append(suggestion_id)
    seen: set[str] = set()
    for key in known:
        for activity in groups[key]:
            seen.add(str(activity.id))
    for key in chosen:
        for activity in groups[key]:
            seen.add(str(activity.id))
    batches = _chunks(suggestion_ids, batch_size)
    run.status = "done" if not batches else "queued"
    run.total_activities = len(seen)
    run.labels_total = len(suggestion_ids)
    run.batches_total = len(batches)
    run.finished_at = now if not batches else None
    run.updated_at = now
    _attach_known_reviews(session, run, known, groups, orgs, now)
    session.flush()
    return run, batches


def _groups(
    session: Session,
    *,
    org_id: UUID | None,
) -> dict[str, list[Activity]]:
    pending_review = (
        select(ActivityCategoryReview.id)
        .where(ActivityCategoryReview.activity_id == Activity.id)
        .where(ActivityCategoryReview.status == "pending")
    )
    query = (
        select(Activity)
        .join(Organization, Organization.id == Activity.org_id)
        .where(Organization.review_status == "pending_review")
        .where(Activity.category_id == PENDING_CATEGORY_ID)
        .where(Activity.source_category_name.is_not(None))
        .where(~pending_review.exists())
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


def _catalog(session: Session, keys: list[str]) -> _Catalog:
    exact: dict[str, list[UUID]] = {}
    by_key: dict[str, set[UUID]] = {}
    live: set[UUID] = set()
    for row in session.scalars(select(ActivityCategory)).all():
        if row.id == PENDING_CATEGORY_ID:
            continue
        category_id = UUID(str(row.id))
        live.add(category_id)
        exact.setdefault(row.name, []).append(category_id)
        names = {normalize_category_key(row.name)}
        translations = row.name_translations or {}
        if isinstance(translations, dict):
            for value in translations.values():
                if isinstance(value, str) and value.strip():
                    names.add(normalize_category_key(value))
        for name in names:
            if name:
                by_key.setdefault(name, set()).add(category_id)
    suggestions: dict[str, CategorySuggestion] = {}
    if keys:
        found = session.scalars(
            select(CategorySuggestion).where(CategorySuggestion.fingerprint.in_(keys))
        ).all()
        suggestions = {row.fingerprint: row for row in found}
    return _Catalog(exact, by_key, live, suggestions)


def _orgs(
    session: Session,
    groups: dict[str, list[Activity]],
) -> dict[str, Organization]:
    ids = {row.org_id for rows in groups.values() for row in rows}
    if not ids:
        return {}
    found = session.scalars(select(Organization).where(Organization.id.in_(ids))).all()
    return {str(org.id): org for org in found}


def _split(
    catalog: _Catalog,
    groups: dict[str, list[Activity]],
) -> tuple[dict[str, UUID], dict[str, list[Activity]]]:
    known: dict[str, UUID] = {}
    unknown: dict[str, list[Activity]] = {}
    for key, rows in groups.items():
        target = _known_target(catalog, rows)
        if target is None:
            unknown[key] = rows
        else:
            known[key] = target
    return known, unknown


def _known_target(
    catalog: _Catalog,
    rows: list[Activity],
) -> UUID | None:
    name = _preferred_name([row.source_category_name or "" for row in rows])
    exact = catalog.exact.get(name, [])
    if len(exact) > 1:
        return None
    if len(exact) == 1:
        return exact[0]
    alias = _alias_target(catalog, name)
    if alias is not None:
        return alias
    normalized = normalize_category_key(name)
    if not normalized:
        return None
    found = catalog.by_key.get(normalized, set())
    if len(found) == 1:
        return next(iter(found))
    return None


def _alias_target(catalog: _Catalog, name: str) -> UUID | None:
    fingerprint = normalize_category_key(name)
    if not fingerprint:
        return None
    suggestion = catalog.suggestions.get(fingerprint)
    if suggestion is None:
        return None
    raw = suggestion.created_category_id or suggestion.merged_into_category_id
    if raw is None:
        return None
    target = UUID(str(raw))
    if target == PENDING_CATEGORY_ID or target not in catalog.live_ids:
        return None
    return target


def _preview_enqueue(
    catalog: _Catalog,
    key: str,
    rows: list[Activity],
    *,
    rescan: bool,
) -> bool:
    if _known_target(catalog, rows) is not None:
        return False
    suggestion = catalog.suggestions.get(key)
    if suggestion is None:
        return True
    if suggestion.status != "pending":
        return False
    previous = int(suggestion.activity_count or 0)
    projected = max(previous, len(rows))
    return _should_enqueue(
        suggestion,
        rescan=rescan,
        created=False,
        linked=projected > previous,
        previous=previous,
        count=projected,
    )


def _attach_known_reviews(
    session: Session,
    run: CategoryScanRun,
    known: dict[str, UUID],
    groups: dict[str, list[Activity]],
    orgs: dict[str, Organization],
    now: datetime,
) -> None:
    if not known:
        return
    _audit_scan(session, run.id)
    activity_ids = [str(row.id) for key in known for row in groups[key]]
    overridden = _left_alone(session, activity_ids)
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
                org=orgs.get(str(activity.org_id)),
                overridden=str(activity.id) in overridden,
                now=now,
            )


def _left_alone(session: Session, activity_ids: list[str]) -> set[str]:
    if not activity_ids:
        return set()
    rows = session.scalars(
        select(ActivityCategoryReview.activity_id).where(
            ActivityCategoryReview.activity_id.in_(activity_ids),
            ActivityCategoryReview.status.in_(_LEAVE),
        )
    ).all()
    return {str(item) for item in rows}


def _move_known(
    session: Session,
    run: CategoryScanRun,
    activity: Activity,
    target: ActivityCategory,
    *,
    org: Organization | None,
    overridden: bool,
    now: datetime,
) -> None:
    if org is None or org.review_status != "pending_review":
        return
    if str(activity.category_id) != str(PENDING_CATEGORY_ID):
        return
    if str(activity.category_id) == str(target.id):
        return
    previous = UUID(str(activity.category_id))
    can_auto = not overridden
    if can_auto:
        activity.category_id = target.id
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
    catalog: _Catalog,
    orgs: dict[str, Organization],
    key: str,
    rows: list[Activity],
    *,
    rescan: bool,
    allow_enqueue: bool,
) -> str | None:
    repo = CategorySuggestionRepository(session)
    suggestion = catalog.suggestions.get(key)
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
        catalog.suggestions[key] = suggestion
        created = True
    elif suggestion.status != "pending":
        # Rejected, approved, and merged labels stay decided. Discover
        # still records activities imported after that decision.
        _link_rows(session, suggestion, rows, orgs)
        repo.refresh_activity_count(suggestion)
        return None
    previous = int(suggestion.activity_count or 0)
    linked = _link_rows(session, suggestion, rows, orgs)
    count = repo.refresh_activity_count(suggestion)
    if not allow_enqueue or not _should_enqueue(
        suggestion,
        rescan=rescan,
        created=created,
        linked=linked,
        previous=previous,
        count=count,
    ):
        return None
    return str(suggestion.id)


def _link_rows(
    session: Session,
    suggestion: CategorySuggestion,
    rows: list[Activity],
    orgs: dict[str, Organization],
) -> bool:
    linked = False
    for activity in rows:
        org = orgs.get(str(activity.org_id))
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
    return linked


def _should_enqueue(
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
