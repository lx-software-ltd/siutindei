"""List and forget organizations an admin delete kept out of import."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.admin_auth import _set_session_audit_context
from app.api.admin_request import _query_param, parse_limit
from app.db.engine import get_engine
from app.exceptions import ValidationError
from app.services.org_delete import (
    forget_deleted_organization,
    list_deleted_organizations,
)
from app.utils import json_response


def handle_deleted_organizations(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
) -> dict[str, Any]:
    """Dispatch /v1/admin/deleted-organizations routes."""
    if method == "GET" and resource_id is None:
        return _list(event)
    if method == "DELETE" and resource_id:
        return _forget(event, resource_id)
    return json_response(404, {"error": "Not found"}, event=event)


def _list(event: Mapping[str, Any]) -> dict[str, Any]:
    with Session(get_engine()) as session:
        payload = list_deleted_organizations(
            session,
            query=_query_param(event, "q"),
            cursor=_query_param(event, "cursor"),
            limit=parse_limit(event),
        )
    return json_response(200, payload, event=event)


def _forget(event: Mapping[str, Any], resource_id: str) -> dict[str, Any]:
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        forget_deleted_organization(session, _uuid(resource_id))
        session.commit()
    return json_response(204, {}, event=event)


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValidationError("id must be a UUID", field="id") from exc
