"""Store one category-check batch and apply high-confidence reassignments."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.audit import set_audit_context
from app.db.models import Activity, ActivityCategory, Organization
from app.db.models.category_scan import ActivityCategoryReview, CategoryScanRun
from app.db.models.category_suggestion import PENDING_CATEGORY_ID
from app.services.category_suggestions.settings import get_settings

_OVERRIDE = ("dismissed", "reverted")


def store_scan_batch(
    session: Session,
    run_id: UUID,
    activity_ids: list[str],
    parsed: Any,
    usage: dict[str, Any] | None,
    *,
    message_id: str = "",
) -> bool:
    """Persist verdicts for one batch. Return False when the message was stored."""
    run = session.get(CategoryScanRun, run_id)
    if run is None or run.status in {"done", "failed"}:
        return False
    if not _claim_message(run, message_id):
        return False
    ids = [item for item in (_uuid(value) for value in activity_ids) if item]
    activities = (
        list(session.scalars(select(Activity).where(Activity.id.in_(ids))).all())
        if ids
        else []
    )
    by_id = {str(activity.id): activity for activity in activities}
    org_ids = {activity.org_id for activity in activities}
    orgs = {
        str(org.id): org
        for org in (
            session.scalars(
                select(Organization).where(Organization.id.in_(org_ids))
            ).all()
            if org_ids
            else []
        )
    }
    overridden = _overridden(session, list(by_id))
    threshold = _threshold(session)
    results = _index_results(parsed)
    counts = {
        "confirmed": 0,
        "auto_applied": 0,
        "reassign_pending": 0,
        "proposed": 0,
        "skipped": 0,
        "failed": 0,
    }
    now = datetime.now(timezone.utc)
    proposals: list[tuple[Activity, dict[str, Any]]] = []
    for activity_id in ids:
        activity = by_id.get(str(activity_id))
        if activity is None:
            counts["skipped"] += 1
            continue
        result = results.get(str(activity_id))
        if not isinstance(result, dict):
            counts["failed"] += 1
            continue
        verdict = result.get("verdict")
        if verdict == "propose":
            proposals.append((activity, result))
            continue
        _record_direct(
            session,
            run,
            activity,
            orgs.get(str(activity.org_id)),
            result,
            threshold=threshold,
            overridden=str(activity.id) in overridden,
            counts=counts,
            now=now,
        )
    from app.services.category_suggestions.scan_proposals import record_proposals

    record_proposals(
        session,
        run,
        proposals,
        orgs,
        counts,
        now,
        threshold=threshold,
        overridden=overridden,
    )
    _bump(run, counts, usage or {}, now)
    session.flush()
    return True


def record_batch_failure(
    session: Session,
    run_id: UUID,
    activity_ids: list[str],
    message: str,
    *,
    message_id: str = "",
) -> None:
    """Count a batch that exhausted retries."""
    run = session.get(CategoryScanRun, run_id)
    if run is None or run.status in {"done", "failed"}:
        return
    if not _claim_message(run, message_id):
        return
    run.failed = int(run.failed or 0) + len(activity_ids)
    run.error = message[:500]
    _bump(run, {}, {}, datetime.now(timezone.utc))
    session.flush()


def _record_direct(
    session: Session,
    run: CategoryScanRun,
    activity: Activity,
    org: Organization | None,
    result: dict[str, Any],
    *,
    threshold: float | None,
    overridden: bool,
    counts: dict[str, int],
    now: datetime,
) -> None:
    verdict = result.get("verdict")
    confidence = _confidence(result.get("confidence"))
    rationale = _text(result.get("rationale"))
    current_id = _uuid(activity.category_id)
    if verdict == "confirm":
        status = "pending" if current_id == PENDING_CATEGORY_ID else "confirmed"
        if status == "confirmed":
            counts["confirmed"] += 1
        else:
            counts["reassign_pending"] += 1
        _add_review(
            session,
            run=run,
            activity=activity,
            verdict="confirm",
            status=status,
            confidence=confidence,
            rationale=rationale,
            now=now,
        )
        return
    if verdict != "reassign":
        counts["failed"] += 1
        return
    target = _category(session, result.get("category_id"))
    if target is None:
        counts["failed"] += 1
        return
    _apply_reassign(
        session,
        run,
        activity,
        org,
        target,
        confidence=confidence,
        rationale=rationale,
        threshold=threshold,
        overridden=overridden,
        counts=counts,
        now=now,
    )


def _apply_reassign(
    session: Session,
    run: CategoryScanRun,
    activity: Activity,
    org: Organization | None,
    target: ActivityCategory,
    *,
    confidence: float | None,
    rationale: str | None,
    threshold: float | None,
    overridden: bool,
    counts: dict[str, int],
    now: datetime,
    suggestion_id: UUID | None = None,
) -> None:
    org_open = org is not None and org.review_status == "pending_review"
    can_auto = (
        org_open
        and not overridden
        and threshold is not None
        and confidence is not None
        and confidence >= threshold
    )
    status = "pending"
    previous = None
    if can_auto:
        _audit_scan(session, run.id)
        previous = _uuid(activity.category_id)
        activity.category_id = target.id  # type: ignore[assignment]
        status = "auto_applied"
        counts["auto_applied"] += 1
    else:
        counts["reassign_pending"] += 1
    _add_review(
        session,
        run=run,
        activity=activity,
        verdict="reassign",
        status=status,
        confidence=confidence,
        rationale=rationale,
        now=now,
        proposed_category_id=_uuid(target.id),
        suggestion_id=suggestion_id,
        previous_category_id=previous,
        decided_by=f"category-scan:{run.id}" if can_auto else None,
    )


def _add_review(
    session: Session,
    *,
    run: CategoryScanRun,
    activity: Activity,
    verdict: str,
    status: str,
    confidence: float | None,
    rationale: str | None,
    now: datetime,
    proposed_category_id: UUID | None = None,
    suggestion_id: UUID | None = None,
    previous_category_id: UUID | None = None,
    decided_by: str | None = None,
) -> None:
    existing = session.execute(
        select(ActivityCategoryReview).where(
            ActivityCategoryReview.scan_run_id == run.id,
            ActivityCategoryReview.activity_id == activity.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    decided = status in {"confirmed", "auto_applied"}
    session.add(
        ActivityCategoryReview(
            scan_run_id=run.id,
            activity_id=activity.id,
            org_id=activity.org_id,
            current_category_id=_uuid(activity.category_id)
            if status != "auto_applied"
            else previous_category_id,
            verdict=verdict,
            proposed_category_id=proposed_category_id,
            suggestion_id=suggestion_id,
            confidence=confidence,
            rationale=rationale,
            status=status,
            previous_category_id=previous_category_id,
            decided_by=decided_by,
            decided_at=now if decided else None,
        )
    )


def _bump(
    run: CategoryScanRun,
    counts: dict[str, int],
    usage: dict[str, Any],
    now: datetime,
) -> None:
    for key, amount in counts.items():
        setattr(run, key, int(getattr(run, key) or 0) + amount)
    cost = usage.get("cost_usd") or 0
    run.cost_usd = Decimal(str(run.cost_usd or 0)) + Decimal(str(round(float(cost), 6)))
    run.batches_done = int(run.batches_done or 0) + 1
    run.updated_at = now
    if run.status == "queued":
        run.status = "running"
    if int(run.batches_done or 0) >= int(run.batches_total or 0):
        run.finished_at = now
        run.status = "failed" if run.error else "done"


def _claim_message(run: CategoryScanRun, message_id: str) -> bool:
    if not message_id:
        return True
    seen = [str(item) for item in (run.processed_message_ids or []) if item]
    if message_id in seen:
        return False
    seen.append(message_id)
    run.processed_message_ids = seen[-200:]
    return True


def _overridden(session: Session, activity_ids: list[str]) -> set[str]:
    if not activity_ids:
        return set()
    rows = session.scalars(
        select(ActivityCategoryReview.activity_id).where(
            ActivityCategoryReview.activity_id.in_(activity_ids),
            ActivityCategoryReview.status.in_(_OVERRIDE),
        )
    ).all()
    return {str(item) for item in rows}


def _threshold(session: Session) -> float | None:
    raw = get_settings(session).auto_assign_threshold
    if raw is None:
        return None
    return float(raw)


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
        activity_id = str(item.get("activity_id") or "").strip()
        if activity_id:
            indexed[activity_id] = item
    return indexed


def _category(session: Session, raw: Any) -> ActivityCategory | None:
    category_id = _uuid(raw)
    if category_id is None or category_id == PENDING_CATEGORY_ID:
        return None
    return session.get(ActivityCategory, category_id)


def _audit_scan(session: Session, run_id: UUID) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    set_audit_context(
        session,
        user_id=f"category-scan:{run_id}",
        request_id=str(run_id),
    )


def _confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number < 0 or number > 1:
        return None
    return round(number, 3)


def _name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text[:200]


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:2000] if text else None


def _uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return UUID(value.strip())
    except ValueError:
        return None
