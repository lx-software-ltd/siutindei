"""Admin settings for category capture and the OpenRouter model."""

from __future__ import annotations

from typing import Any
from typing import Mapping

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_request import _parse_body
from app.db.engine import get_engine
from app.exceptions import ValidationError
from app.services.category_suggestions.settings import (
    apply_settings_update,
    get_settings,
    serialize_settings,
)
from app.services.openrouter_client import (
    WORKLOAD_CATEGORY_SETTINGS_TEST,
    OpenRouterError,
    extract_message_text,
    openrouter_chat_completion,
    usage_from_body,
)
from app.utils import json_response

# API Gateway REST integrations time out at 29s and the admin Lambda
# timeout is 30s, so this call stays at one attempt of about 15s.
SETTINGS_TEST_TIMEOUT_SECONDS = 15


def handle_settings(
    event: Mapping[str, Any],
    method: str,
    sub_resource: str | None,
) -> dict[str, Any]:
    """GET/PUT settings and POST settings/test."""
    if method == "GET" and sub_resource is None:
        return _handle_get(event)
    if method == "PUT" and sub_resource is None:
        return _handle_put(event)
    if method == "POST" and sub_resource == "test":
        return _handle_test(event)
    return json_response(404, {"error": "Not found"}, event=event)


def _handle_get(event: Mapping[str, Any]) -> dict[str, Any]:
    with Session(get_engine()) as session:
        return json_response(
            200,
            serialize_settings(get_settings(session)),
            event=event,
        )


def _handle_put(event: Mapping[str, Any]) -> dict[str, Any]:
    body = _object_body(event)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        row = apply_settings_update(
            session,
            body,
            updated_by=_get_user_sub(event),
        )
        payload = serialize_settings(row)
        session.commit()
        return json_response(200, payload, event=event)


def _handle_test(event: Mapping[str, Any]) -> dict[str, Any]:
    body = _object_body(event)
    model = body.get("model")
    model_name = (
        str(model).strip() if isinstance(model, str) and model.strip() else None
    )
    try:
        raw = openrouter_chat_completion(
            system_prompt="Reply with the single word ok.",
            user_content="ping",
            timeout=SETTINGS_TEST_TIMEOUT_SECONDS,
            workload=WORKLOAD_CATEGORY_SETTINGS_TEST,
            temperature=0,
            max_attempts=1,
            model=model_name,
        )
    except OpenRouterError as exc:
        return json_response(
            502,
            {"error": str(exc)},
            event=event,
        )
    return json_response(
        200,
        {
            "ok": True,
            "message": extract_message_text(raw)[:500],
            "usage": usage_from_body(raw),
        },
        event=event,
    )


def _object_body(event: Mapping[str, Any]) -> dict[str, Any]:
    raw = event.get("body") or ""
    if not str(raw).strip():
        return {}
    body = _parse_body(event)
    if not isinstance(body, dict):
        raise ValidationError("Request body must be an object")
    return body
