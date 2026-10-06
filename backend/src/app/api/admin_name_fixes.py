"""Admin routes for reviewing cleaned organization and activity names."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_request import _query_param, parse_limit, parse_object_body
from app.db.engine import get_engine
from app.exceptions import ValidationError
from app.services.name_fixes import (
    decide_bulk,
    decide_proposal,
    list_proposals,
    preview_name,
    scan_names,
    settings_payload,
    summarize_proposals,
    update_settings,
)
from app.services.name_sanitizer import RULE_CODES
from app.utils import json_response

_STATUSES = {"pending", "applied", "dismissed"}
_ENTITY_TYPES = {"organization", "activity"}


def handle_name_fixes(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch /v1/admin/name-fixes routes."""
    if method == "GET" and resource_id is None:
        return _list(event)
    if method == "GET" and resource_id == "summary" and sub_resource is None:
        return _summary(event)
    if resource_id == "settings" and sub_resource is None and method == "GET":
        return _settings(event)
    if resource_id == "settings" and sub_resource is None and method == "PUT":
        return _update_settings(event)
    if resource_id == "settings" and sub_resource == "preview" and method == "POST":
        return _preview(event)
    if method == "POST" and resource_id == "scan" and sub_resource is None:
        return _scan(event)
    if method == "POST" and resource_id == "bulk" and sub_resource is None:
        return _bulk(event)
    if method == "POST" and resource_id and sub_resource is None:
        return _decide(event, resource_id)
    return json_response(404, {"error": "Not found"}, event=event)


def _list(event: Mapping[str, Any]) -> dict[str, Any]:
    status = _choice(_query_param(event, "status"), _STATUSES, "status") or "pending"
    entity_type = _choice(
        _query_param(event, "entity_type"), _ENTITY_TYPES, "entity_type"
    )
    org_raw = _blank(_query_param(event, "org_id"))
    with Session(get_engine()) as session:
        payload = list_proposals(
            session,
            status=status,
            entity_type=entity_type,
            rule=_choice(_query_param(event, "rule"), set(RULE_CODES), "rule"),
            org_id=_uuid(org_raw, "org_id") if org_raw else None,
            query=_blank(_query_param(event, "q")),
            limit=parse_limit(event),
        )
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


def _preview(event: Mapping[str, Any]) -> dict[str, Any]:
    body = parse_object_body(event)
    name = body.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name is required", field="name")
    translations = body.get("name_translations") or {}
    if not isinstance(translations, dict):
        raise ValidationError(
            "name_translations must be an object", field="name_translations"
        )
    with Session(get_engine()) as session:
        payload = preview_name(session, name, translations)
    return json_response(200, payload, event=event)


def _scan(event: Mapping[str, Any]) -> dict[str, Any]:
    body = parse_object_body(event)
    entity_type = _choice(body.get("entity_type"), _ENTITY_TYPES, "entity_type")
    org_raw = body.get("org_id")
    query = body.get("q")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = scan_names(
            session,
            entity_type=entity_type,
            org_id=_uuid(str(org_raw), "org_id") if org_raw else None,
            query=query.strip() if isinstance(query, str) and query.strip() else None,
        )
        session.commit()
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
    action = body.get("action")
    if action not in {"apply", "dismiss"}:
        raise ValidationError("action must be apply or dismiss", field="action")
    value = body.get("value")
    if value is not None and not isinstance(value, str):
        raise ValidationError("value must be a string", field="value")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = decide_proposal(
            session,
            _uuid(raw_id, "id"),
            action,
            value,
            _get_user_sub(event),
        )
        session.commit()
    return json_response(200, payload, event=event)


def _choice(value: Any, allowed: set[str], field: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text not in allowed:
        raise ValidationError(f"Invalid {field}", field=field)
    return text


def _uuid(value: str, field: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("id must be a UUID", field=field) from exc


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None
