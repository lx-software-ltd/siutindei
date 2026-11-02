"""User organization lookup handlers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.api.admin_auth import _set_session_audit_context
from app.api.admin_request import _query_param
from app.db.engine import get_engine
from app.db.repositories import OrganizationRepository
from app.exceptions import ValidationError
from app.utils import json_response, parse_int


def _handle_user_organizations(
    event: Mapping[str, Any],
    method: str,
) -> dict[str, Any]:
    """Search organizations by name for authenticated users."""
    if method != "GET":
        return json_response(405, {"error": "Method not allowed"}, event=event)

    query = (_query_param(event, "q") or "").strip()
    limit = parse_int(_query_param(event, "limit")) or 20
    if limit < 1 or limit > 50:
        raise ValidationError("limit must be between 1 and 50", field="limit")

    if not query:
        return json_response(200, {"items": []}, event=event)

    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = OrganizationRepository(session)
        results = repo.search_by_name(query, limit=limit)
        return json_response(
            200,
            {"items": [{"id": str(org.id), "name": org.name} for org in results]},
            event=event,
        )
