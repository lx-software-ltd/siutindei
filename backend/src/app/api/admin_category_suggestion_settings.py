"""Admin settings for category capture and the OpenRouter model."""

from __future__ import annotations

from typing import Any
from typing import Mapping

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_request import parse_object_body
from app.db.engine import get_engine
from app.services.category_suggestions.settings import (
    apply_settings_update,
    get_settings,
    resolved_fallback_models,
    resolved_model_name,
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
    override = str(model).strip() if isinstance(model, str) and model.strip() else None
    model_name, fallbacks, deny = _test_call_settings(override)
    try:
        raw = openrouter_chat_completion(
            system_prompt="Reply with the single word ok.",
            user_content="ping",
            timeout=SETTINGS_TEST_TIMEOUT_SECONDS,
            workload=WORKLOAD_CATEGORY_SETTINGS_TEST,
            temperature=0,
            max_attempts=1,
            model=model_name,
            fallback_models=fallbacks,
            deny_data_collection=deny,
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
    return parse_object_body(event)


def _test_call_settings(override: str | None) -> tuple[str, list[str], bool]:
    """Read the saved model for this call so a settings save is immediate."""
    with Session(get_engine()) as session:
        row = get_settings(session)
        stored = override if override is not None else row.openrouter_model
        return (
            resolved_model_name(stored),
            resolved_fallback_models(row.fallback_models),
            bool(row.deny_data_collection),
        )
