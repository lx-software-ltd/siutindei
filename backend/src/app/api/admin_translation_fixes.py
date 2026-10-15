"""Admin routes for reviewing missing translations."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_list_filters import _blank
from app.api.admin_request import (
    _query_param,
    parse_limit,
    parse_object_body,
    uuid_resource_id,
)
from app.db.engine import get_engine
from app.db.models.translation_fix import TranslationScanRun
from app.services.data_quality.sweep_support import mark_scan_enqueue_failed
from app.exceptions import ValidationError
from app.services.category_suggestions.events import enqueue_translation_batches
from app.services.translation_fix_query import (
    ENTITY_TYPES,
    FIELDS,
    STATUSES,
    choice,
    get_proposal,
    list_proposals,
    parse_uuid,
    settings_payload,
    summarize_proposals,
    update_settings,
)
from app.services.translation_fix_scan import (
    TranslationScanBusy,
    start_translation_scan,
)
from app.services.translation_fixes import decide_bulk, decide_proposal
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)

_REVIEW_SCOPES = frozenset({"pending_review", "all"})


def handle_translation_fixes(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch /v1/admin/translation-fixes routes."""
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
    item_id = uuid_resource_id(resource_id)
    if method == "GET" and item_id and sub_resource is None:
        return _get(event, item_id)
    if method == "POST" and item_id and sub_resource is None:
        return _decide(event, item_id)
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
            field=choice(_query_param(event, "field"), FIELDS, "field"),
            org_id=parse_uuid(org_raw, "org_id") if org_raw else None,
            query=_blank(_query_param(event, "q")),
            cursor=_blank(_query_param(event, "cursor")),
            limit=parse_limit(event),
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
            payload, batches = start_translation_scan(
                session,
                review_scope=review_scope,
                entity_type=choice(
                    body.get("entity_type"), ENTITY_TYPES, "entity_type"
                ),
                org_id=parse_uuid(str(org_raw), "org_id") if org_raw else None,
                query=query.strip()
                if isinstance(query, str) and query.strip()
                else None,
                requested_by=_get_user_sub(event),
            )
        except TranslationScanBusy:
            return json_response(
                409,
                {"error": "A translation sweep is already running"},
                event=event,
            )
        run_id = payload["scan_run_id"]
        session.commit()
    if batches:
        try:
            enqueue_translation_batches(run_id, batches)
        except Exception:
            logger.exception("Translation sweep enqueue failed")
            mark_scan_enqueue_failed(
                TranslationScanRun,
                run_id,
                "Translation sweep could not be queued",
            )
            return json_response(
                502,
                {"error": "Translation sweep could not be queued"},
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
    action = body.get("action")
    if action not in {"apply", "dismiss"}:
        raise ValidationError("action must be apply or dismiss", field="action")
    translations = body.get("translations")
    if translations is not None and not isinstance(translations, dict):
        raise ValidationError("translations must be an object", field="translations")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = decide_proposal(
            session,
            parse_uuid(raw_id, "id"),
            action,
            _get_user_sub(event),
            translations=translations,
        )
        session.commit()
    return json_response(200, payload, event=event)
