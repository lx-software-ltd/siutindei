"""Admin routes that start and read category-check runs."""

from __future__ import annotations

from typing import Any
from typing import Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_request import parse_object_body
from app.db.engine import get_engine
from app.db.models.category_scan import CategoryScanRun
from app.exceptions import ValidationError
from app.services.category_suggestions.events import (
    enqueue_discover_batches,
    enqueue_scan_batches,
)
from app.services.category_suggestions.scan import (
    CategoryScanBusy,
    list_runs,
    serialize_run,
    start_scan,
)
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)


def handle_scan(
    event: Mapping[str, Any],
    method: str,
    sub_resource: str | None,
) -> dict[str, Any]:
    """POST /scan, GET /scan, and GET /scan/{id}."""
    if method == "POST" and sub_resource is None:
        return _start(event)
    if method == "GET" and sub_resource is None:
        return _list(event)
    if method == "GET" and sub_resource:
        return _detail(event, sub_resource)
    return json_response(404, {"error": "Not found"}, event=event)


def _start(event: Mapping[str, Any]) -> dict[str, Any]:
    body = parse_object_body(event)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        try:
            run, batches = start_scan(
                session,
                body,
                requested_by=_get_user_sub(event),
            )
        except CategoryScanBusy:
            return json_response(
                409,
                {"error": "A category check is already running"},
                event=event,
            )
        payload = serialize_run(run)
        run_id = str(run.id)
        mode = run.mode
        session.commit()
    if batches:
        try:
            enqueue = (
                enqueue_discover_batches if mode == "discover" else enqueue_scan_batches
            )
            enqueue(run_id, batches)
        except Exception:
            logger.exception("Category check enqueue failed")
            _mark_enqueue_failed(run_id)
            return json_response(
                502,
                {"error": "Category check could not be queued"},
                event=event,
            )
    return json_response(202, payload, event=event)


def _list(event: Mapping[str, Any]) -> dict[str, Any]:
    with Session(get_engine()) as session:
        items = [serialize_run(run) for run in list_runs(session)]
        session.commit()
    return json_response(200, {"items": items}, event=event)


def _detail(event: Mapping[str, Any], raw_id: str) -> dict[str, Any]:
    run_id = _parse_uuid(raw_id)
    with Session(get_engine()) as session:
        run = session.get(CategoryScanRun, run_id)
        if run is None:
            return json_response(404, {"error": "Not found"}, event=event)
        return json_response(200, serialize_run(run), event=event)


def _mark_enqueue_failed(run_id: str) -> None:
    with Session(get_engine()) as session:
        run = session.get(CategoryScanRun, UUID(run_id))
        if run is None or run.status in {"done", "failed"}:
            return
        run.status = "failed"
        run.error = "Category check could not be queued"
        session.commit()


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Invalid UUID", field="id") from exc
