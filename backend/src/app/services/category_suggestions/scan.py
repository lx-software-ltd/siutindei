"""Start a category check and run one queued batch."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.models import Activity, Organization
from app.db.models.category_scan import ActivityCategoryReview, CategoryScanRun
from app.exceptions import ValidationError
from app.services.category_suggestions.prompt import build_scan_prompt
from app.services.category_suggestions.scan_apply import (
    record_batch_failure,
    store_scan_batch,
)
from app.services.category_suggestions.settings import (
    get_settings,
    resolved_fallback_models,
    resolved_model_name,
)
from app.services.category_suggestions.scan_candidates import (
    count_candidates as count_candidates,
    select_candidate_ids as select_candidate_ids,
)
from app.services.data_quality.answers import (
    CATEGORY_PROMPT_VERSION,
    recorded_completion,
    recording_flags,
)
from app.services.openrouter_client import (
    WORKLOAD_CATEGORY_SUGGESTION,
    OpenRouterError,
    extract_message_text,
    openrouter_chat_completion,
)
from app.services.openrouter_json_parse import loads_openrouter_json
from app.utils.logging import get_logger

logger = get_logger(__name__)

SKIP_WINDOW = timedelta(days=30)
STALE_AFTER = timedelta(seconds=660)
DEFAULT_LIMIT = 500
MAX_LIMIT = 500
DEFAULT_BATCH_SIZE = 10
MAX_BATCH_SIZE = 20
_SETTLED = ("confirmed", "applied", "auto_applied")
_ACTIVE = ("queued", "running")


class CategoryScanBusy(Exception):
    """A category check is already queued or running."""


def start_scan(
    session: Session,
    body: dict[str, Any],
    *,
    requested_by: str | None,
) -> tuple[CategoryScanRun, list[list[str]]]:
    """Create a run and return id batches to enqueue after commit."""
    _fail_stale_runs(session)
    _reject_over_budget(session)
    active = session.scalar(
        select(CategoryScanRun.id).where(CategoryScanRun.status.in_(_ACTIVE)).limit(1)
    )
    if active is not None:
        raise CategoryScanBusy()
    org_id = _optional_uuid(body.get("org_id"), "org_id")
    if org_id is not None and session.get(Organization, org_id) is None:
        raise ValidationError("org_id not found", field="org_id")
    limit = _bounded_int(body.get("limit", DEFAULT_LIMIT), "limit", 1, MAX_LIMIT)
    batch_size = _bounded_int(
        body.get("batch_size", DEFAULT_BATCH_SIZE),
        "batch_size",
        1,
        MAX_BATCH_SIZE,
    )
    rescan = _parse_bool(body.get("rescan", False), "rescan")
    ignore_current = _parse_bool(
        body.get("ignore_current_category", False),
        "ignore_current_category",
    )
    review_scope = _parse_review_scope(body.get("review_scope"))
    mode = _parse_mode(body.get("mode", "verify"))
    if mode == "discover":
        if ignore_current:
            raise ValidationError(
                "ignore_current_category applies to verify only",
                field="ignore_current_category",
            )
        from app.services.category_suggestions.scan_discover import start_discover

        return start_discover(
            session,
            requested_by=requested_by,
            org_id=org_id,
            limit=limit,
            batch_size=batch_size,
            rescan=rescan,
            review_scope=review_scope,
        )
    if ignore_current:
        rescan = True
    from app.services.category_suggestions.scan_candidates import resolve_scan_ids

    raw_ids = body.get("activity_ids")
    ids = resolve_scan_ids(
        session,
        org_id=org_id,
        limit=limit,
        rescan=rescan,
        review_scope=review_scope,
        activity_ids=raw_ids if isinstance(raw_ids, list) else None,
    )
    now = datetime.now(timezone.utc)
    batches = _chunks([str(item) for item in ids], batch_size)
    run = CategoryScanRun(
        status="done" if not batches else "queued",
        requested_by=requested_by,
        org_id=org_id,
        batch_size=batch_size,
        ignore_current_category=ignore_current,
        total_activities=len(ids),
        batches_total=len(batches),
        finished_at=now if not batches else None,
        updated_at=now,
    )
    try:
        with session.begin_nested():
            session.add(run)
            session.flush()
    except IntegrityError as exc:
        raise CategoryScanBusy() from exc
    return run, batches


def summary_counts(
    session: Session,
    *,
    org_id: UUID | None = None,
) -> dict[str, Any]:
    """Counts the category-check tab and the suggestion summary share."""

    def _count(status: str) -> int:
        return int(
            session.scalar(
                select(func.count())
                .select_from(ActivityCategoryReview)
                .where(ActivityCategoryReview.status == status)
            )
            or 0
        )

    _fail_stale_runs(session)
    from app.services.category_suggestions.scan_discover import count_discover

    discover_activities, discover_labels = count_discover(session, org_id=org_id)
    active = session.scalars(
        select(CategoryScanRun)
        .where(CategoryScanRun.status.in_(_ACTIVE))
        .order_by(CategoryScanRun.created_at.desc())
        .limit(1)
    ).first()
    return {
        "review_pending_total": _count("pending"),
        "auto_applied_total": _count("auto_applied"),
        "scan_candidate_total": count_candidates(session, org_id=org_id),
        "scan_candidate_total_all": count_candidates(
            session, org_id=org_id, review_scope="all"
        ),
        "scan_limit": MAX_LIMIT,
        "scan_batch_size": DEFAULT_BATCH_SIZE,
        "discover_activity_total": discover_activities,
        "discover_label_total": discover_labels,
        "active_scan_run": None if active is None else serialize_run(active),
        "month_scan_cost_usd": _month_scan_cost(session),
    }


def list_runs(session: Session, *, limit: int = 20) -> list[CategoryScanRun]:
    """Recent category-check runs, newest first."""
    _fail_stale_runs(session)
    return list(
        session.scalars(
            select(CategoryScanRun)
            .order_by(CategoryScanRun.created_at.desc())
            .limit(limit)
        ).all()
    )


def serialize_run(run: CategoryScanRun) -> dict[str, Any]:
    """Serialize a category-check run for the admin API."""
    return {
        "id": str(run.id),
        "status": run.status,
        "requested_by": run.requested_by,
        "org_id": None if run.org_id is None else str(run.org_id),
        "mode": run.mode or "verify",
        "ignore_current_category": bool(run.ignore_current_category),
        "batch_size": int(run.batch_size),
        "total_activities": int(run.total_activities or 0),
        "batches_total": int(run.batches_total or 0),
        "labels_total": int(run.labels_total or 0),
        "batches_done": int(run.batches_done or 0),
        "confirmed": int(run.confirmed or 0),
        "auto_applied": int(run.auto_applied or 0),
        "reassign_pending": int(run.reassign_pending or 0),
        "proposed": int(run.proposed or 0),
        "skipped": int(run.skipped or 0),
        "failed": int(run.failed or 0),
        "cost_usd": float(run.cost_usd or 0),
        "error": run.error,
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
        "finished_at": _iso(run.finished_at),
    }


def process_scan_batch(
    scan_run_id: UUID,
    activity_ids: list[str],
    *,
    message_id: str = "",
    receive_count: int = 1,
) -> bool:
    """Classify one batch. Return True when the SQS message can be deleted."""
    prepared = _prepare(scan_run_id, activity_ids, message_id)
    if prepared is None:
        return True
    system, user, model_name, fallbacks, deny, record, refresh = prepared
    try:
        reply = recorded_completion(
            record=record,
            refresh=refresh,
            prompt_version=CATEGORY_PROMPT_VERSION,
            model=model_name,
            system_prompt=system,
            user_content=user,
            invoke=lambda: openrouter_chat_completion(
                system_prompt=system,
                user_content=user,
                timeout=_timeout_seconds(),
                workload=WORKLOAD_CATEGORY_SUGGESTION,
                temperature=0,
                max_attempts=1,
                model=model_name,
                fallback_models=fallbacks,
                deny_data_collection=deny,
            ),
        )
        parsed = loads_openrouter_json(
            extract_message_text(reply.body),
            context="category check",
        )
        usage = reply.usage
    except OpenRouterError as exc:
        if receive_count >= 3:
            _fail(scan_run_id, activity_ids, str(exc), message_id)
        raise
    except Exception as exc:
        logger.exception(
            "Category check batch failed",
            extra={"scan_run_id": str(scan_run_id)},
        )
        _fail(scan_run_id, activity_ids, str(exc) or type(exc).__name__, message_id)
        return True
    with Session(get_engine()) as session:
        reply.keep(session)
        store_scan_batch(
            session,
            scan_run_id,
            activity_ids,
            parsed,
            usage,
            message_id=message_id,
        )
        session.commit()
    return True


def _prepare(
    scan_run_id: UUID,
    activity_ids: list[str],
    message_id: str,
) -> tuple[str, str, str, list[str], bool, bool, bool] | None:
    with Session(get_engine()) as session:
        run = session.get(CategoryScanRun, scan_run_id)
        if run is None or run.status in {"done", "failed"}:
            return None
        seen = [str(item) for item in (run.processed_message_ids or [])]
        if message_id and message_id in seen:
            return None
        ids = [UUID(item) for item in activity_ids]
        activities = list(
            session.scalars(select(Activity).where(Activity.id.in_(ids))).all()
        )
        if not activities:
            store_scan_batch(
                session,
                scan_run_id,
                activity_ids,
                {"results": []},
                {},
                message_id=message_id,
            )
            session.commit()
            return None
        if _over_budget(session):
            now = datetime.now(timezone.utc)
            run.status = "failed"
            run.error = "Monthly category-check budget is used"
            run.finished_at = now
            run.updated_at = now
            session.commit()
            return None
        settings = get_settings(session)
        system, user = build_scan_prompt(
            session,
            activities,
            ignore_current_category=bool(run.ignore_current_category),
        )
        record, refresh = recording_flags(session, run.data_quality_run_id)
        return (
            system,
            user,
            resolved_model_name(settings.openrouter_model),
            resolved_fallback_models(settings.fallback_models),
            bool(settings.deny_data_collection),
            record,
            refresh,
        )


def _fail(
    scan_run_id: UUID,
    activity_ids: list[str],
    message: str,
    message_id: str,
) -> None:
    with Session(get_engine()) as session:
        record_batch_failure(
            session,
            scan_run_id,
            activity_ids,
            message,
            message_id=message_id,
        )
        session.commit()


def _month_start() -> datetime:
    return datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )


def _month_scan_cost(session: Session) -> float:
    value = session.scalar(
        select(func.coalesce(func.sum(CategoryScanRun.cost_usd), 0)).where(
            CategoryScanRun.created_at >= _month_start()
        )
    )
    return float(value or 0)


def _over_budget(session: Session) -> bool:
    limit = get_settings(session).monthly_cost_limit_usd
    return _month_scan_cost(session) >= float(limit)


def _reject_over_budget(session: Session) -> None:
    if _over_budget(session):
        raise ValidationError(
            "Monthly category-check budget is used",
            field="monthly_cost_limit_usd",
        )


def _fail_stale_runs(session: Session) -> None:
    cutoff = datetime.now(timezone.utc) - STALE_AFTER
    now = datetime.now(timezone.utc)
    stale = session.scalars(
        select(CategoryScanRun).where(
            CategoryScanRun.status.in_(_ACTIVE),
            or_(
                CategoryScanRun.updated_at < cutoff,
                CategoryScanRun.updated_at.is_(None),
            ),
        )
    ).all()
    for run in stale:
        run.status = "failed"
        run.error = "No batch completed before the scan went stale"
        run.finished_at = now
        run.updated_at = now
        if run.data_quality_run_id is not None:
            from app.services.data_quality.runs import settle_data_quality_run

            settle_data_quality_run(session, run.data_quality_run_id)


def _chunks(ids: list[str], size: int) -> list[list[str]]:
    return [ids[index : index + size] for index in range(0, len(ids), size)]


def _timeout_seconds() -> int:
    import os

    raw = os.getenv("CATEGORY_SUGGESTION_OPENROUTER_TIMEOUT_SECONDS", "90")
    try:
        return max(10, int(raw))
    except ValueError:
        return 90


def _bounded_int(value: Any, field: str, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be an integer", field=field) from exc
    if parsed < low or parsed > high:
        raise ValidationError(
            f"{field} must be between {low} and {high}",
            field=field,
        )
    return parsed


def _parse_mode(value: Any) -> str:
    if value in (None, ""):
        return "verify"
    if value in {"verify", "discover"}:
        return str(value)
    raise ValidationError("mode must be verify or discover", field="mode")


def _parse_review_scope(value: Any) -> str:
    if value in (None, "", "pending_review"):
        return "pending_review"
    if value == "all":
        return "all"
    raise ValidationError("Invalid review_scope", field="review_scope")


def _parse_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false", "1", "0"}:
        return value.strip().lower() in {"true", "1"}
    raise ValidationError(f"{field} must be a boolean", field=field)


def _optional_uuid(value: Any, field: str) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid {field}", field=field) from exc


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
