"""POST and GET /v1/admin/data-quality/runs."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub
from app.api.admin_request import parse_object_body
from app.db.engine import get_engine
from app.db.models import DataQualityRun
from app.exceptions import NotFoundError, ValidationError
from app.services.data_quality.runs import (
    create_manual_run,
    enqueue_staged_run,
    retry_run,
    serialize_run,
)
from app.utils import json_response


def handle_data_quality(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch /data-quality/runs and /data-quality/runs/{id}."""
    if resource_id != "runs":
        return json_response(404, {"error": "Not found"}, event=event)
    if method == "GET" and sub_resource is None:
        return _list(event)
    if method == "POST" and sub_resource is None:
        return _create(event)
    if sub_resource is None:
        return json_response(404, {"error": "Not found"}, event=event)
    if method == "GET":
        return _get(event, sub_resource)
    if method == "POST":
        return _retry(event, sub_resource)
    return json_response(404, {"error": "Not found"}, event=event)


def _list(event: Mapping[str, Any]) -> dict[str, Any]:
    with Session(get_engine()) as session:
        rows = session.scalars(
            select(DataQualityRun)
            .order_by(DataQualityRun.created_at.desc(), DataQualityRun.id.desc())
            .limit(50)
        ).all()
        payload = {"items": [serialize_run(row, summary=True) for row in rows]}
    return json_response(200, payload, event=event)


def _create(event: Mapping[str, Any]) -> dict[str, Any]:
    body = parse_object_body(event)
    with Session(get_engine()) as session:
        run = create_manual_run(session, body, requested_by=_get_user_sub(event))
        payload = serialize_run(run)
        run_id = str(run.id)
        session.commit()
    enqueue_staged_run(run_id)
    return json_response(200, payload, event=event)


def _get(event: Mapping[str, Any], raw_id: str) -> dict[str, Any]:
    run_id = _parse_id(raw_id)
    with Session(get_engine()) as session:
        run = session.get(DataQualityRun, run_id)
        if run is None:
            raise NotFoundError("data-quality", raw_id)
        summary = _status_view(event)
        payload = serialize_run(run, summary=summary)
    return json_response(200, payload, event=event)


def _retry(event: Mapping[str, Any], raw_id: str) -> dict[str, Any]:
    body = parse_object_body(event)
    if body.get("action") != "retry":
        raise ValidationError("action must be retry", field="action")
    run_id = _parse_id(raw_id)
    with Session(get_engine()) as session:
        run = session.get(DataQualityRun, run_id)
        if run is None:
            raise NotFoundError("data-quality", raw_id)
        refresh = body.get("refresh", False)
        if not isinstance(refresh, bool):
            raise ValidationError("refresh must be a boolean", field="refresh")
        send = retry_run(session, run, refresh=refresh)
        payload = serialize_run(run)
        session.commit()
    if send:
        enqueue_staged_run(str(run_id))
    return json_response(200, payload, event=event)


def _status_view(event: Mapping[str, Any]) -> bool:
    params = event.get("queryStringParameters") or {}
    return params.get("view") == "status"


def _parse_id(raw_id: str) -> UUID:
    try:
        return UUID(raw_id)
    except ValueError as exc:
        raise ValidationError("id must be a UUID", field="id") from exc
