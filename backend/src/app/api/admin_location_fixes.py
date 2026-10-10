"""Admin routes for reviewing organization and activity venues."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_request import _query_param, parse_limit, parse_object_body
from app.db.engine import get_engine
from app.db.models.location_fix import LocationScanRun
from app.exceptions import ValidationError
from app.services.category_suggestions.events import enqueue_location_batches
from app.services.location_fix_scan import LocationScanBusy, start_location_scan
from app.services.location_fix_query import (
    ENTITY_TYPES,
    GRADES,
    KINDS,
    SOURCES,
    STATUSES,
    choice,
    get_proposal,
    list_proposals,
    parse_uuid,
    settings_payload,
    summarize_proposals,
    update_settings,
)
from app.services.location_fixes import decide_bulk, decide_proposal
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)

_REVIEW_SCOPES = frozenset({"pending_review", "all"})


def handle_location_fixes(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch /v1/admin/location-fixes routes."""
    if method == "GET" and resource_id is None:
        return _list(event)
    if method == "GET" and resource_id == "summary" and sub_resource is None:
        return _summary(event)
    if resource_id == "settings" and sub_resource is None and method == "GET":
        return _settings(event)
    if resource_id == "settings" and sub_resource is None and method == "PUT":
        return _update_settings(event)
    if method == "POST" and resource_id == "scan" and sub_resource is None:
        return _scan(event)
    if method == "POST" and resource_id == "bulk" and sub_resource is None:
        return _bulk(event)
    if method == "GET" and _item_id(resource_id) and sub_resource is None:
        return _get(event, resource_id)
    if method == "POST" and _item_id(resource_id) and sub_resource is None:
        return _decide(event, resource_id)
    return json_response(404, {"error": "Not found"}, event=event)


def _list(event: Mapping[str, Any]) -> dict[str, Any]:
    status = choice(_query_param(event, "status"), STATUSES, "status") or "pending"
    org_raw = _blank(_query_param(event, "org_id"))
    with Session(get_engine()) as session:
        payload = list_proposals(
            session,
            status=status,
            entity_type=choice(
                _query_param(event, "entity_type"), ENTITY_TYPES, "entity_type"
            ),
            kind=choice(_query_param(event, "kind"), KINDS, "kind"),
            source=choice(_query_param(event, "source"), SOURCES, "source"),
            org_id=parse_uuid(org_raw, "org_id") if org_raw else None,
            query=_blank(_query_param(event, "q")),
            cursor=_blank(_query_param(event, "cursor")),
            limit=parse_limit(event),
            grade=choice(_query_param(event, "grade"), GRADES, "grade"),
        )
    return json_response(200, payload, event=event)


def _get(event: Mapping[str, Any], raw_id: str) -> dict[str, Any]:
    with Session(get_engine()) as session:
        payload = get_proposal(session, parse_uuid(raw_id, "id"))
    return json_response(200, payload, event=event)


def _summary(event: Mapping[str, Any]) -> dict[str, Any]:
    with Session(get_engine()) as session:
        payload = summarize_proposals(session)
    return json_response(200, payload, event=event)


def _settings(event: Mapping[str, Any]) -> dict[str, Any]:
    with Session(get_engine()) as session:
        payload = settings_payload(session)
    return json_response(200, payload, event=event)


def _update_settings(event: Mapping[str, Any]) -> dict[str, Any]:
    body = parse_object_body(event)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = update_settings(session, body)
        session.commit()
    return json_response(200, payload, event=event)


def _scan(event: Mapping[str, Any]) -> dict[str, Any]:
    body = parse_object_body(event)
    review_scope = choice(body.get("review_scope"), _REVIEW_SCOPES, "review_scope")
    if review_scope is None:
        raise ValidationError("review_scope is required", field="review_scope")
    org_raw = body.get("org_id")
    query = body.get("q")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        try:
            payload, batches = start_location_scan(
                session,
                review_scope=review_scope,
                entity_type=choice(
                    body.get("entity_type"), ENTITY_TYPES, "entity_type"
                ),
                org_id=parse_uuid(str(org_raw), "org_id") if org_raw else None,
                query=query.strip()
                if isinstance(query, str) and query.strip()
                else None,
                lookup=_lookup(body.get("lookup")),
                requested_by=_get_user_sub(event),
            )
        except LocationScanBusy:
            return json_response(
                409,
                {"error": "A location sweep is already running"},
                event=event,
            )
        run_id = payload["scan_run_id"]
        session.commit()
    if batches:
        try:
            enqueue_location_batches(run_id, batches)
        except Exception:
            logger.exception("Location sweep enqueue failed")
            _mark_enqueue_failed(run_id)
            return json_response(
                502,
                {"error": "Location sweep could not be queued"},
                event=event,
            )
    return json_response(200, payload, event=event)


def _bulk(event: Mapping[str, Any]) -> dict[str, Any]:
    body = parse_object_body(event)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = decide_bulk(session, body, _get_user_sub(event))
        if not body.get("dry_run"):
            session.commit()
    return json_response(200, payload, event=event)


def _decide(event: Mapping[str, Any], raw_id: str) -> dict[str, Any]:
    body = parse_object_body(event)
    return _decide_body(event, parse_uuid(raw_id, "id"), body, _get_user_sub(event))


def _decide_body(
    event: Mapping[str, Any],
    proposal_id: UUID,
    body: dict[str, Any],
    decided_by: str | None,
) -> dict[str, Any]:
    action = body.get("action")
    if action not in {"apply", "dismiss"}:
        raise ValidationError("action must be apply or dismiss", field="action")
    address = body.get("address")
    area_id = body.get("area_id")
    target_raw = body.get("target_location_id")
    if address is not None and not isinstance(address, str):
        raise ValidationError("address must be a string", field="address")
    if area_id is not None and not isinstance(area_id, str):
        raise ValidationError("area_id must be a string", field="area_id")
    target_location_id = None
    lat = _coord(body.get("lat"), "lat")
    lng = _coord(body.get("lng"), "lng")
    if target_raw is not None:
        if not isinstance(target_raw, str) or not target_raw.strip():
            raise ValidationError(
                "target_location_id must be a UUID", field="target_location_id"
            )
        target_location_id = parse_uuid(target_raw, "target_location_id")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = decide_proposal(
            session,
            proposal_id,
            action,
            decided_by,
            address=address,
            area_id=area_id,
            target_location_id=target_location_id,
            lat=lat,
            lng=lng,
        )
        session.commit()
    return json_response(200, payload, event=event)


def _mark_enqueue_failed(run_id: str) -> None:
    with Session(get_engine()) as session:
        run = session.get(LocationScanRun, UUID(run_id))
        if run is None or run.status in {"done", "failed"}:
            return
        run.status = "failed"
        run.error = "Location sweep could not be queued"
        session.commit()


def _item_id(resource_id: str | None) -> bool:
    if resource_id is None:
        return False
    try:
        UUID(resource_id)
    except ValueError:
        return False
    return True


def _lookup(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValidationError("lookup must be a string", field="lookup")
    return value.strip() or None


def _coord(value: Any, field: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be a number", field=field)
    return float(value)


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None
