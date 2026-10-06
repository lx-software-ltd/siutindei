"""Run one discovery batch and auto-map a confident existing category."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_scan import ActivityCategoryReview, CategoryScanRun
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    CategorySuggestion,
    CategorySuggestionActivity,
)
from app.db.repositories.category_suggestion import CategorySuggestionRepository
from app.services.category_suggestions.prompt import build_discovery_prompt
from app.services.category_suggestions.reviews import apply_suggestion_to_reviews
from app.services.category_suggestions.scan_apply import (
    _add_review,
    _audit_scan,
    _bump,
    _claim_message,
    _confidence,
    _overridden,
    _threshold,
    record_batch_failure,
)
from app.services.category_suggestions.settings import (
    get_settings,
    resolved_fallback_models,
    resolved_model_name,
)
from app.services.openrouter_client import (
    WORKLOAD_CATEGORY_SUGGESTION,
    OpenRouterError,
    extract_message_text,
    openrouter_chat_completion,
    usage_from_body,
)
from app.services.openrouter_json_parse import loads_openrouter_json
from app.utils.logging import get_logger

logger = get_logger(__name__)


def process_discover_batch(
    scan_run_id: UUID,
    suggestion_ids: list[str],
    *,
    message_id: str = "",
    receive_count: int = 1,
) -> bool:
    """Enrich one label batch. Return True when the SQS message can be deleted."""
    prepared = _prepare(scan_run_id, suggestion_ids, message_id)
    if prepared is None:
        return True
    system, user, model_name, fallbacks, deny = prepared
    try:
        body = openrouter_chat_completion(
            system_prompt=system,
            user_content=user,
            timeout=_timeout_seconds(),
            workload=WORKLOAD_CATEGORY_SUGGESTION,
            temperature=0,
            max_attempts=1,
            model=model_name,
            fallback_models=fallbacks,
            deny_data_collection=deny,
        )
        parsed = loads_openrouter_json(
            extract_message_text(body),
            context="category discovery",
        )
        usage = usage_from_body(body)
    except OpenRouterError as exc:
        if receive_count >= 3:
            _fail(scan_run_id, suggestion_ids, str(exc), message_id)
        raise
    except Exception as exc:
        logger.exception(
            "Category discovery batch failed",
            extra={"scan_run_id": str(scan_run_id)},
        )
        _fail(
            scan_run_id,
            suggestion_ids,
            str(exc) or type(exc).__name__,
            message_id,
        )
        return True
    with Session(get_engine()) as session:
        store_discover_batch(
            session,
            scan_run_id,
            suggestion_ids,
            parsed,
            usage,
            message_id,
        )
        session.commit()
    return True


def store_discover_batch(
    session: Session,
    run_id: UUID,
    suggestion_ids: list[str],
    parsed: Any,
    usage: dict[str, Any],
    message_id: str,
) -> None:
    """Apply one discovery result and auto-map when confidence is high enough."""
    from app.services.category_suggestions.enrich import _apply_parsed

    run = session.get(CategoryScanRun, run_id)
    if run is None or run.status in {"done", "failed"}:
        return
    if not _claim_message(run, message_id):
        return
    indexed = _index_results(parsed)
    counts = {"auto_applied": 0, "failed": 0}
    now = datetime.now(timezone.utc)
    threshold = _threshold(session)
    audited = False
    for raw_id in suggestion_ids:
        suggestion = _suggestion(session, raw_id)
        result = indexed.get(raw_id)
        if suggestion is None or not isinstance(result, dict):
            counts["failed"] += 1
            continue
        _apply_parsed(session, suggestion, result, usage)
        maps_confidence = _maps_confidence(result)
        if suggestion.maps_to_category_id is not None:
            suggestion.confidence = maps_confidence
        if not _can_auto_map(suggestion, threshold):
            continue
        target = session.get(ActivityCategory, suggestion.maps_to_category_id)
        if target is None:
            continue
        if not audited:
            _audit_scan(session, run.id)
            audited = True
        moved = _move_linked(session, run, suggestion, target, now)
        apply_suggestion_to_reviews(
            session,
            suggestion,
            target_id=UUID(str(target.id)),
            decided_by=f"category-scan:{run.id}",
        )
        counts["auto_applied"] += moved
        suggestion.status = "merged"
        suggestion.merged_into_category_id = target.id  # type: ignore[assignment]
        suggestion.decided_by = f"category-scan:{run.id}"
        suggestion.decided_at = now
        suggestion.updated_at = now
        CategorySuggestionRepository(session).refresh_activity_count(suggestion)
    _bump(run, counts, usage, now)
    session.flush()


def _prepare(
    scan_run_id: UUID,
    suggestion_ids: list[str],
    message_id: str,
) -> tuple[str, str, str, list[str], bool] | None:
    with Session(get_engine()) as session:
        run = session.get(CategoryScanRun, scan_run_id)
        if run is None or run.status in {"done", "failed"}:
            return None
        seen = [str(item) for item in (run.processed_message_ids or [])]
        if message_id and message_id in seen:
            return None
        from app.services.category_suggestions.scan import _over_budget

        if _over_budget(session):
            now = datetime.now(timezone.utc)
            run.status = "failed"
            run.error = "Monthly category-check budget is used"
            run.finished_at = now
            run.updated_at = now
            session.commit()
            return None
        ids = [UUID(item) for item in suggestion_ids]
        suggestions = list(
            session.scalars(
                select(CategorySuggestion).where(CategorySuggestion.id.in_(ids))
            ).all()
        )
        if not suggestions:
            store_discover_batch(
                session,
                scan_run_id,
                suggestion_ids,
                {"results": []},
                {},
                message_id,
            )
            session.commit()
            return None
        settings = get_settings(session)
        system, user = build_discovery_prompt(session, suggestions)
        return (
            system,
            user,
            resolved_model_name(settings.openrouter_model),
            resolved_fallback_models(settings.fallback_models),
            bool(settings.deny_data_collection),
        )


def _maps_confidence(result: dict[str, Any]) -> float | None:
    """Confidence that this label is an existing category, not the proposal."""
    maps = result.get("maps_to_existing")
    if not isinstance(maps, dict):
        return None
    return _confidence(maps.get("confidence"))


def _can_auto_map(suggestion: CategorySuggestion, threshold: float | None) -> bool:
    if suggestion.status != "pending" or suggestion.reopened_at is not None:
        return False
    if suggestion.maps_to_category_id is None or threshold is None:
        return False
    confidence = suggestion.confidence
    if confidence is None:
        return False
    return float(confidence) >= threshold


def _move_linked(
    session: Session,
    run: CategoryScanRun,
    suggestion: CategorySuggestion,
    target: ActivityCategory,
    now: datetime,
) -> int:
    links = list(
        session.scalars(
            select(CategorySuggestionActivity).where(
                CategorySuggestionActivity.suggestion_id == suggestion.id
            )
        ).all()
    )
    if not links:
        return 0
    activities = list(
        session.scalars(
            select(Activity).where(
                Activity.id.in_([link.activity_id for link in links])
            )
        ).all()
    )
    overridden = _overridden(session, [str(item.id) for item in activities])
    moved = 0
    for activity in activities:
        org = session.get(Organization, activity.org_id)
        if org is None or org.review_status != "pending_review":
            continue
        if str(activity.id) in overridden:
            continue
        if _has_open_review(session, activity.id):
            continue
        if str(activity.category_id) != str(PENDING_CATEGORY_ID):
            continue
        if str(activity.category_id) == str(target.id):
            continue
        previous = UUID(str(activity.category_id))
        activity.category_id = target.id
        _add_review(
            session,
            run=run,
            activity=activity,
            verdict="reassign",
            status="auto_applied",
            confidence=float(suggestion.confidence or 0),
            rationale=suggestion.rationale,
            now=now,
            proposed_category_id=UUID(str(target.id)),
            suggestion_id=UUID(str(suggestion.id)),
            previous_category_id=previous,
            decided_by=f"category-scan:{run.id}",
        )
        moved += 1
    return moved


def _has_open_review(session: Session, activity_id: Any) -> bool:
    row = session.scalar(
        select(ActivityCategoryReview.id)
        .where(ActivityCategoryReview.activity_id == activity_id)
        .where(ActivityCategoryReview.status == "pending")
        .limit(1)
    )
    return row is not None


def _fail(
    scan_run_id: UUID,
    suggestion_ids: list[str],
    message: str,
    message_id: str,
) -> None:
    with Session(get_engine()) as session:
        record_batch_failure(
            session,
            scan_run_id,
            suggestion_ids,
            message,
            message_id=message_id,
        )
        session.commit()


def _suggestion(session: Session, raw_id: str) -> CategorySuggestion | None:
    try:
        suggestion_id = UUID(raw_id)
    except ValueError:
        return None
    return session.get(CategorySuggestion, suggestion_id)


def _index_results(parsed: Any) -> dict[str, dict[str, Any]]:
    raw_items: Any
    if isinstance(parsed, dict):
        raw_items = parsed.get("results", [])
    elif isinstance(parsed, list):
        raw_items = parsed
    else:
        raw_items = []
    indexed: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_items, list):
        return indexed
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        suggestion_id = str(item.get("suggestion_id") or "").strip()
        if suggestion_id:
            indexed[suggestion_id] = item
    return indexed


def _timeout_seconds() -> int:
    import os

    raw = os.getenv("CATEGORY_SUGGESTION_OPENROUTER_TIMEOUT_SECONDS", "90")
    try:
        return max(10, int(raw))
    except ValueError:
        return 90
