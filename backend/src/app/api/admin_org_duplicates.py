"""Admin routes that find and merge duplicate organizations."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _set_session_audit_context
from app.api.admin_request import _query_param, parse_limit, parse_object_body
from app.db.engine import get_engine
from app.exceptions import ValidationError
from app.services.org_duplicates import (
    DEFAULT_MIN_SCORE,
    dismiss_pairs,
    get_duplicate_group,
    list_duplicate_groups,
    search_organizations,
)
from app.services.org_merge import merge_organizations
from app.services.org_merge_media import delete_merged_media
from app.utils import json_response


def handle_org_duplicates(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
    sub_resource: str | None,
) -> dict[str, Any]:
    """Dispatch /v1/admin/org-duplicates routes."""
    if sub_resource is not None:
        return json_response(404, {"error": "Not found"}, event=event)
    if method == "GET" and resource_id is None:
        return _list(event)
    if method == "GET" and resource_id == "search":
        return _search(event)
    if method == "GET" and resource_id:
        return _get(event, resource_id)
    if method == "POST" and resource_id == "dismiss":
        return _dismiss(event)
    if method == "POST" and resource_id == "merge":
        return _merge(event)
    return json_response(404, {"error": "Not found"}, event=event)


def _list(event: Mapping[str, Any]) -> dict[str, Any]:
    min_score = _parse_score(_query_param(event, "min_score"))
    with Session(get_engine()) as session:
        payload = list_duplicate_groups(
            session,
            min_score=min_score,
            signal=_blank(_query_param(event, "signal")),
            source=_blank(_query_param(event, "source")),
            review_status=_blank(_query_param(event, "review_status")),
            query=_blank(_query_param(event, "q")),
            org_id=_blank(_query_param(event, "org_id")),
            cursor=_blank(_query_param(event, "cursor")),
            limit=parse_limit(event),
        )
    return json_response(200, payload, event=event)


def _get(event: Mapping[str, Any], group_id: str) -> dict[str, Any]:
    with Session(get_engine()) as session:
        payload = get_duplicate_group(session, group_id)
    return json_response(200, payload, event=event)


def _search(event: Mapping[str, Any]) -> dict[str, Any]:
    query = _blank(_query_param(event, "q"))
    if query is None or len(query) < 2:
        raise ValidationError("q must be at least 2 characters", field="q")
    with Session(get_engine()) as session:
        items = search_organizations(session, query)
    return json_response(200, {"items": items}, event=event)


def _dismiss(event: Mapping[str, Any]) -> dict[str, Any]:
    body = parse_object_body(event)
    org_ids = _uuid_list(body.get("org_ids"), "org_ids", minimum=2)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        created = dismiss_pairs(session, org_ids, _get_user_sub(event))
        session.commit()
    return json_response(200, {"dismissed_pairs": created}, event=event)


def _merge(event: Mapping[str, Any]) -> dict[str, Any]:
    body = parse_object_body(event)
    survivor_id = _uuid(body.get("survivor_id"), "survivor_id")
    source_ids = _uuid_list(body.get("source_ids"), "source_ids", minimum=1)
    overrides = body.get("field_overrides") or {}
    if not isinstance(overrides, dict):
        raise ValidationError(
            "field_overrides must be an object", field="field_overrides"
        )
    dry_run = bool(body.get("dry_run"))
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        payload = merge_organizations(
            session,
            survivor_id,
            source_ids,
            overrides,
            dry_run=dry_run,
            merged_by=_get_user_sub(event),
        )
        if not dry_run:
            session.commit()
    if not dry_run:
        delete_merged_media(list(payload.get("pending_deletes") or []))
    status = 200 if dry_run else 201
    return json_response(status, _public_plan(payload), event=event)


def _public_plan(payload: dict[str, Any]) -> dict[str, Any]:
    hidden = {"values", "pending_deletes"}
    return {key: value for key, value in payload.items() if key not in hidden}


def _parse_score(value: str | None) -> float:
    if value is None or value.strip() == "":
        return DEFAULT_MIN_SCORE
    try:
        score = float(value)
    except ValueError as exc:
        raise ValidationError("min_score must be a number", field="min_score") from exc
    if score < 0 or score > 1:
        raise ValidationError("min_score must be between 0 and 1", field="min_score")
    return score


def _uuid_list(value: Any, field: str, minimum: int) -> list[UUID]:
    if not isinstance(value, list):
        raise ValidationError(f"{field} must be a list", field=field)
    parsed = list(dict.fromkeys(_uuid(item, field) for item in value))
    if len(parsed) < minimum:
        raise ValidationError(f"At least {minimum} ids are required", field=field)
    return parsed


def _uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("id must be a UUID", field=field) from exc


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None
