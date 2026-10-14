"""Run one data-quality check and record its checkpoint."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, CategoryScanRun, LocationScanRun
from app.db.models.category_scan import ActivityCategoryReview
from app.exceptions import ValidationError
from app.services.category_suggestions.scan import CategoryScanBusy, start_scan
from app.services.category_suggestions.settings import (
    get_settings,
    resolved_model_name,
)
from app.services.data_quality.categories import category_input_hash
from app.services.data_quality.duplicates import report_duplicates
from app.services.location_fix_scan import LocationScanBusy, start_location_scan

_TERMINAL = frozenset(
    {"done", "unchanged", "skipped", "failed", "busy", "over_budget", "partial"}
)
_OPEN = frozenset({"queued", "running"})


def run_check(session: Session, run, check: dict[str, Any]) -> dict[str, Any]:
    """Execute one check. Child scans return batches to enqueue after commit."""
    name = check.get("name")
    if name == "names":
        return _names(session, run)
    if name == "duplicates":
        return _duplicates(session, run)
    if name == "locations":
        return _locations(session, run, check)
    if name == "categories":
        return _categories(session, run, check)
    return {"status": "skipped", "detail": {}}


def refresh_check(session: Session, run, check: dict[str, Any]) -> None:
    """Move a child scan's checkpoint when that scan has finished."""
    name = check.get("name")
    if name == "locations":
        _refresh_location(session, run, check)
    elif name == "categories":
        _refresh_category(session, run, check)


def _names(session: Session, run) -> dict[str, Any]:
    from app.services.name_fix_scan import scan_names

    scope = run.scope or {}
    result = scan_names(
        session,
        review_scope="all",
        org_ids=_uuids(scope.get("organization_ids")),
        activity_ids=_uuids(scope.get("activity_ids")),
    )
    status = "unchanged" if _names_quiet(result) else "done"
    return {"status": status, "detail": result, "batches": []}


def _duplicates(session: Session, run) -> dict[str, Any]:
    scope = run.scope or {}
    report = report_duplicates(session, list(scope.get("organization_ids") or []))
    previous = _previous_detail(run, "duplicates")
    status = "unchanged" if previous == report else "done"
    return {"status": status, "detail": report, "batches": []}


def _locations(session: Session, run, check: dict[str, Any]) -> dict[str, Any]:
    detail = dict(check.get("detail") or {})
    existing = _location_child(session, run.id)
    resumed = _resume_open_child(existing, detail, "location")
    if resumed is not None:
        return resumed
    scope = run.scope or {}
    org_ids = _uuids(scope.get("organization_ids"))
    try:
        payload, batches = start_location_scan(
            session,
            review_scope="all",
            only_org_ids=org_ids,
            budget_seconds=None,
            reuse_lookups=True,
            batch_size=1,
            requested_by=run.requested_by,
        )
    except LocationScanBusy:
        return {"status": "busy", "detail": detail, "batches": []}
    except ValidationError as exc:
        if exc.field == "monthly_cost_limit_usd":
            return {
                "status": "over_budget",
                "detail": {"error": "over_budget"},
                "batches": [],
            }
        return {"status": "failed", "detail": {"error": exc.message}, "batches": []}
    child = session.get(LocationScanRun, UUID(str(payload["id"])))
    if child is not None:
        child.data_quality_run_id = run.id
    detail["scan_run_id"] = payload["id"]
    detail["pending_batches"] = batches
    if not batches:
        return {"status": "done", "detail": detail, "batches": []}
    return {
        "status": "running",
        "detail": detail,
        "batches": batches,
        "batch_kind": "location",
    }


def _categories(session: Session, run, check: dict[str, Any]) -> dict[str, Any]:
    detail = dict(check.get("detail") or {})
    existing = _category_child(session, run.id)
    resumed = _resume_open_child(existing, detail, "category")
    if resumed is not None:
        return resumed
    scope = run.scope or {}
    from app.services.category_suggestions.scan import MAX_LIMIT

    wanted = [str(item) for item in (scope.get("activity_ids") or [])]
    ids = _fresh_activity_ids(session, wanted)
    detail["skipped_unchanged"] = len(wanted) - len(ids)
    if not ids:
        status = "unchanged" if detail["skipped_unchanged"] else "done"
        return {"status": status, "detail": detail, "batches": []}
    chosen = ids[:MAX_LIMIT]
    detail["truncated"] = len(ids) > MAX_LIMIT
    try:
        child, batches = start_scan(
            session,
            {
                "activity_ids": chosen,
                "limit": len(chosen),
                "batch_size": 1,
                "review_scope": "all",
                "rescan": True,
                "mode": "verify",
            },
            requested_by=run.requested_by,
        )
    except CategoryScanBusy:
        return {"status": "busy", "detail": detail, "batches": []}
    except ValidationError as exc:
        if "budget" in exc.message.casefold():
            return {
                "status": "over_budget",
                "detail": {"error": "over_budget"},
                "batches": [],
            }
        return {"status": "failed", "detail": {"error": exc.message}, "batches": []}
    child.data_quality_run_id = run.id
    detail["scan_run_id"] = str(child.id)
    detail["pending_batches"] = batches
    if not batches:
        return {"status": _noted(detail, "done"), "detail": detail, "batches": []}
    return {
        "status": "running",
        "detail": detail,
        "batches": batches,
        "batch_kind": "category",
    }


def _fresh_activity_ids(session: Session, activity_ids: list[str]) -> list[str]:
    parsed = _uuids(activity_ids)
    if not parsed:
        return []
    activities = list(
        session.scalars(select(Activity).where(Activity.id.in_(parsed))).all()
    )
    settings = get_settings(session)
    threshold = settings.auto_assign_threshold
    model = resolved_model_name(settings.openrouter_model)
    hashes = {
        str(activity.id): category_input_hash(
            activity,
            model=model,
            threshold=None if threshold is None else float(threshold),
        )
        for activity in activities
    }
    rows = session.execute(
        select(
            ActivityCategoryReview.activity_id,
            ActivityCategoryReview.input_hash,
            ActivityCategoryReview.status,
        ).where(ActivityCategoryReview.activity_id.in_(parsed))
    ).all()
    settled = {
        str(activity_id)
        for activity_id, digest, status in rows
        if status in {"pending", "confirmed", "applied", "auto_applied"}
        and digest
        and digest == hashes.get(str(activity_id))
    }
    ordered = sorted(
        activities, key=lambda activity: (str(activity.created_at), str(activity.id))
    )
    return [str(activity.id) for activity in ordered if str(activity.id) not in settled]


def _names_quiet(result: dict[str, Any]) -> bool:
    return not any(
        int(result.get(key) or 0) for key in ("created", "updated", "cleared")
    )


def _previous_detail(run, name: str) -> dict[str, Any] | None:
    for item in run.checks or []:
        if isinstance(item, dict) and item.get("name") == name:
            detail = item.get("detail")
            return detail if isinstance(detail, dict) and detail else None
    return None


def _location_child(session: Session, run_id) -> LocationScanRun | None:
    return session.scalars(
        select(LocationScanRun).where(LocationScanRun.data_quality_run_id == run_id)
    ).first()


def _category_child(session: Session, run_id) -> CategoryScanRun | None:
    return session.scalars(
        select(CategoryScanRun).where(CategoryScanRun.data_quality_run_id == run_id)
    ).first()


def _child_state(
    status: str, detail: dict[str, Any], error: str | None
) -> dict[str, Any]:
    if status in _OPEN:
        return {"status": "running", "detail": detail, "batches": []}
    if status == "failed" or error:
        return {
            "status": "failed",
            "detail": {**detail, "error": error or "failed"},
            "batches": [],
        }
    return {"status": _noted(detail, "done"), "detail": detail, "batches": []}


def _resume_open_child(
    existing, detail: dict[str, Any], kind: str
) -> dict[str, Any] | None:
    """Return queued batches that never left, or the child scan's state."""
    if existing is None:
        return None
    if existing.status not in _OPEN:
        return _child_state(existing.status, detail, existing.error)
    pending = list(detail.get("pending_batches") or [])
    sent = int(getattr(existing, "batches_done", 0) or 0)
    remaining = pending[sent:]
    if not remaining:
        return {"status": "running", "detail": detail, "batches": []}
    return {
        "status": "running",
        "detail": detail,
        "batches": remaining,
        "batch_kind": kind,
    }


def _noted(detail: dict[str, Any], status: str) -> str:
    if detail.get("truncated") and status == "done":
        return "partial"
    return status


def _refresh_location(session: Session, run, check: dict[str, Any]) -> None:
    if check.get("status") not in _OPEN and check.get("status") != "running":
        return
    child = _location_child(session, run.id)
    if child is None or child.status in _OPEN:
        return
    state = _child_state(child.status, dict(check.get("detail") or {}), child.error)
    check["status"] = state["status"]
    check["detail"] = state["detail"]


def _refresh_category(session: Session, run, check: dict[str, Any]) -> None:
    if check.get("status") not in {"running", "queued"}:
        return
    child = _category_child(session, run.id)
    if child is None or child.status in _OPEN:
        return
    state = _child_state(child.status, dict(check.get("detail") or {}), child.error)
    check["status"] = state["status"]
    check["detail"] = state["detail"]


def _uuids(values) -> list[UUID]:
    parsed: list[UUID] = []
    for raw in values or []:
        try:
            parsed.append(UUID(str(raw)))
        except ValueError:
            continue
    return parsed
