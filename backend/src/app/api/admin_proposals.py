"""Admin proposal routes parameterized by kind.

Public paths stay on the existing resources. ``handle_proposals`` is the
shared dispatcher; the old modules are thin aliases.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

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
from app.exceptions import NotFoundError, ValidationError
from app.services.data_quality.list_params import choice, parse_uuid
from app.services.data_quality.proposal_lifecycle import (
    ProposalKind,
    ScanBusy,
    bulk_decide,
    decide,
    get_proposal,
    list_proposals,
    settings_payload,
    start_scan,
    summarize_proposals,
    update_settings,
)
from app.services.data_quality.sweep_support import mark_scan_enqueue_failed
from app.services.location_fix_query import (
    ENTITY_TYPES as LOCATION_ENTITY_TYPES,
)
from app.services.location_fix_query import (
    GRADES,
    KINDS,
    SOURCES,
)
from app.services.location_fix_query import (
    STATUSES as LOCATION_STATUSES,
)
from app.services.name_sanitizer import RULE_CODES
from app.services.translation_fix_query import (
    ENTITY_TYPES as TRANSLATION_ENTITY_TYPES,
)
from app.services.translation_fix_query import (
    FIELDS,
)
from app.services.translation_fix_query import (
    STATUSES as TRANSLATION_STATUSES,
)
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)

_REVIEW_SCOPES = frozenset({"pending_review", "all"})
_NAME_STATUSES = frozenset({"pending", "applied", "dismissed"})
_NAME_ENTITY_TYPES = frozenset({"organization", "activity"})
_ACTIONS = frozenset({"apply", "dismiss"})
_NAME_RULES = frozenset(RULE_CODES)


def handle_proposals(
    event: Mapping[str, Any],
    method: str,
    kind: ProposalKind,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch one proposal resource. ``kind`` selects the table."""
    if (
        kind is ProposalKind.NAMES
        and resource_id == "settings"
        and sub_resource == "preview"
        and method == "POST"
    ):
        return _preview_name(event)
    if method == "GET" and resource_id is None:
        return _list(event, kind)
    if method == "GET" and resource_id == "summary" and sub_resource is None:
        return _summary(event, kind)
    if resource_id == "settings" and sub_resource is None and method == "GET":
        return _settings(event, kind)
    if resource_id == "settings" and sub_resource is None and method == "PUT":
        return _update_settings(event, kind)
    if method == "POST" and resource_id == "scan" and sub_resource is None:
        return _scan(event, kind)
    if method == "POST" and resource_id == "bulk" and sub_resource is None:
        return _bulk(event, kind)
    return _item(event, method, kind, resource_id, sub_resource)


def _list(event: Mapping[str, Any], kind: ProposalKind) -> dict[str, Any]:
    with Session(get_engine()) as session:
        payload = list_proposals(kind, session, **_list_filters(event, kind, session))
    return json_response(200, payload, event=event)


def _list_filters(
    event: Mapping[str, Any],
    kind: ProposalKind,
    session: Session,
) -> dict[str, Any]:
    if kind is ProposalKind.NAMES:
        return _name_list_filters(event, session)
    if kind is ProposalKind.LOCATIONS:
        return _location_list_filters(event)
    return _translation_list_filters(event)


def _translation_list_filters(event: Mapping[str, Any]) -> dict[str, Any]:
    org_raw = _blank(_query_param(event, "org_id"))
    return {
        "status": choice(_query_param(event, "status"), TRANSLATION_STATUSES, "status")
        or "pending",
        "entity_type": choice(
            _query_param(event, "entity_type"),
            TRANSLATION_ENTITY_TYPES,
            "entity_type",
        ),
        "field": choice(_query_param(event, "field"), FIELDS, "field"),
        "org_id": parse_uuid(org_raw, "org_id") if org_raw else None,
        "query": _blank(_query_param(event, "q")),
        "cursor": _blank(_query_param(event, "cursor")),
        "limit": parse_limit(event),
    }


def _location_list_filters(event: Mapping[str, Any]) -> dict[str, Any]:
    org_raw = _blank(_query_param(event, "org_id"))
    return {
        "status": choice(_query_param(event, "status"), LOCATION_STATUSES, "status")
        or "pending",
        "entity_type": choice(
            _query_param(event, "entity_type"),
            LOCATION_ENTITY_TYPES,
            "entity_type",
        ),
        "kind": choice(_query_param(event, "kind"), KINDS, "kind"),
        "source": choice(_query_param(event, "source"), SOURCES, "source"),
        "org_id": parse_uuid(org_raw, "org_id") if org_raw else None,
        "query": _blank(_query_param(event, "q")),
        "cursor": _blank(_query_param(event, "cursor")),
        "limit": parse_limit(event),
        "grade": choice(_query_param(event, "grade"), GRADES, "grade"),
    }


def _name_list_filters(event: Mapping[str, Any], session: Session) -> dict[str, Any]:
    run_raw = _blank(_query_param(event, "run"))
    status = choice(_query_param(event, "status"), _NAME_STATUSES, "status")
    if run_raw is None:
        status = status or "pending"
    organization_ids = None
    activity_ids = None
    if run_raw:
        organization_ids, activity_ids = _run_scope(session, run_raw)
    org_raw = _blank(_query_param(event, "org_id"))
    return {
        "status": status,
        "entity_type": choice(
            _query_param(event, "entity_type"),
            _NAME_ENTITY_TYPES,
            "entity_type",
        ),
        "rule": choice(_query_param(event, "rule"), _NAME_RULES, "rule"),
        "org_id": parse_uuid(org_raw, "org_id") if org_raw else None,
        "query": _blank(_query_param(event, "q")),
        "cursor": _blank(_query_param(event, "cursor")),
        "limit": parse_limit(event),
        "organization_ids": organization_ids,
        "activity_ids": activity_ids,
    }


def _run_scope(session: Session, raw_id: str) -> tuple[list[UUID], list[UUID]]:
    from app.db.models import DataQualityRun

    try:
        run_id = UUID(raw_id)
    except ValueError as exc:
        raise ValidationError("run must be a UUID", field="run") from exc
    run = session.get(DataQualityRun, run_id)
    if run is None:
        raise NotFoundError("data-quality", raw_id)
    scope = run.scope if isinstance(run.scope, dict) else {}
    return (
        [parse_uuid(str(item), "run") for item in scope.get("organization_ids") or []],
        [parse_uuid(str(item), "run") for item in scope.get("activity_ids") or []],
    )


def _summary(event: Mapping[str, Any], kind: ProposalKind) -> dict[str, Any]:
    with Session(get_engine()) as session:
        payload = summarize_proposals(kind, session)
    return json_response(200, payload, event=event)


def _settings(event: Mapping[str, Any], kind: ProposalKind) -> dict[str, Any]:
    with Session(get_engine()) as session:
        payload = settings_payload(kind, session)
    return json_response(200, payload, event=event)


def _update_settings(event: Mapping[str, Any], kind: ProposalKind) -> dict[str, Any]:
    body = parse_object_body(event)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = update_settings(kind, session, body)
        session.commit()
    return json_response(200, payload, event=event)


def _preview_name(event: Mapping[str, Any]) -> dict[str, Any]:
    from app.services.name_fixes import preview_name

    body = parse_object_body(event)
    name = body.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name is required", field="name")
    translations = body.get("name_translations") or {}
    if not isinstance(translations, dict):
        raise ValidationError(
            "name_translations must be an object",
            field="name_translations",
        )
    with Session(get_engine()) as session:
        payload = preview_name(session, name, translations)
    return json_response(200, payload, event=event)


def _scan(event: Mapping[str, Any], kind: ProposalKind) -> dict[str, Any]:
    body = parse_object_body(event)
    kwargs = _scan_kwargs(kind, event, body)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        try:
            started = start_scan(kind, session, **kwargs)
        except ScanBusy as exc:
            return json_response(409, {"error": exc.message}, event=event)
        run_id = started.payload.get("scan_run_id")
        session.commit()
    return _enqueue_scan(event, started, run_id)


def _scan_kwargs(
    kind: ProposalKind,
    event: Mapping[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    review_scope = choice(body.get("review_scope"), _REVIEW_SCOPES, "review_scope")
    if review_scope is None:
        raise ValidationError("review_scope is required", field="review_scope")
    org_raw = body.get("org_id")
    query = body.get("q")
    cleaned_query = query.strip() if isinstance(query, str) and query.strip() else None
    org_id = parse_uuid(str(org_raw), "org_id") if org_raw else None
    if kind is ProposalKind.NAMES:
        return {
            "entity_type": choice(
                body.get("entity_type"),
                _NAME_ENTITY_TYPES,
                "entity_type",
            ),
            "org_id": org_id,
            "query": cleaned_query,
            "review_scope": review_scope,
        }
    entity_types = (
        LOCATION_ENTITY_TYPES
        if kind is ProposalKind.LOCATIONS
        else TRANSLATION_ENTITY_TYPES
    )
    kwargs: dict[str, Any] = {
        "review_scope": review_scope,
        "entity_type": choice(body.get("entity_type"), entity_types, "entity_type"),
        "org_id": org_id,
        "query": cleaned_query,
        "requested_by": _get_user_sub(event),
    }
    if kind is ProposalKind.LOCATIONS:
        kwargs["lookup"] = _lookup(body.get("lookup"))
    return kwargs


def _enqueue_scan(
    event: Mapping[str, Any], started: Any, run_id: Any
) -> dict[str, Any]:
    if (
        started.batches
        and started.enqueue is not None
        and started.run_model is not None
    ):
        try:
            started.enqueue(run_id, started.batches)
        except Exception:
            logger.exception(started.enqueue_log)
            mark_scan_enqueue_failed(started.run_model, run_id, started.enqueue_error)
            return json_response(502, {"error": started.enqueue_error}, event=event)
    return json_response(200, started.payload, event=event)


def _bulk(event: Mapping[str, Any], kind: ProposalKind) -> dict[str, Any]:
    body = parse_object_body(event)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = bulk_decide(kind, session, body, _get_user_sub(event))
        if not body.get("dry_run"):
            session.commit()
    return json_response(200, payload, event=event)


def _item(
    event: Mapping[str, Any],
    method: str,
    kind: ProposalKind,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    if kind is ProposalKind.NAMES:
        if sub_resource is not None or not resource_id:
            return json_response(404, {"error": "Not found"}, event=event)
        if method == "GET":
            return _get(event, kind, parse_uuid(resource_id, "id"))
        if method == "POST":
            return _decide_named(event, parse_uuid(resource_id, "id"))
        return json_response(404, {"error": "Not found"}, event=event)
    if kind is ProposalKind.LOCATIONS:
        item_id = uuid_resource_id(resource_id)
        if method == "POST" and item_id and sub_resource is None:
            from app.api.admin_location_fixes import _decide_body

            return _decide_body(
                event,
                parse_uuid(item_id, "id"),
                parse_object_body(event),
                _get_user_sub(event),
            )
        if method == "GET" and item_id and sub_resource is None:
            return _get(event, kind, parse_uuid(item_id, "id"))
        return json_response(404, {"error": "Not found"}, event=event)
    item_id = uuid_resource_id(resource_id)
    if method == "GET" and item_id and sub_resource is None:
        return _get(event, kind, parse_uuid(item_id, "id"))
    if method == "POST" and item_id and sub_resource is None:
        return _decide_translation(event, parse_uuid(item_id, "id"))
    return json_response(404, {"error": "Not found"}, event=event)


def _get(
    event: Mapping[str, Any],
    kind: ProposalKind,
    proposal_id: UUID,
) -> dict[str, Any]:
    with Session(get_engine()) as session:
        payload = get_proposal(kind, session, proposal_id)
    return json_response(200, payload, event=event)


def _decide_translation(
    event: Mapping[str, Any],
    proposal_id: UUID,
) -> dict[str, Any]:
    body = parse_object_body(event)
    action = _action(body)
    translations = body.get("translations")
    if translations is not None and not isinstance(translations, dict):
        raise ValidationError("translations must be an object", field="translations")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = decide(
            ProposalKind.TRANSLATIONS,
            session,
            proposal_id,
            action,
            _get_user_sub(event),
            translations=translations,
        )
        session.commit()
    return json_response(200, payload, event=event)


def _decide_named(event: Mapping[str, Any], proposal_id: UUID) -> dict[str, Any]:
    body = parse_object_body(event)
    action = _action(body)
    value = body.get("value")
    if value is not None and not isinstance(value, str):
        raise ValidationError("value must be a string", field="value")
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = decide(
            ProposalKind.NAMES,
            session,
            proposal_id,
            action,
            _get_user_sub(event),
            value=value,
        )
        session.commit()
    return json_response(200, payload, event=event)


def _action(body: dict[str, Any]) -> str:
    action = body.get("action")
    if action not in _ACTIONS:
        raise ValidationError("action must be apply or dismiss", field="action")
    return str(action)


def _lookup(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValidationError("lookup must be a string", field="lookup")
    return value.strip() or None
