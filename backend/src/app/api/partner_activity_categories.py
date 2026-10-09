"""Full-access partner list and delete for activity categories."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.api.admin_areas import _build_activity_category_tree
from app.api.admin_auth import _set_session_audit_context
from app.api.admin_request import _parse_uuid
from app.api.admin_resource_activity_category import (
    _serialize_activity_category,
)
from app.api.partner_auth import PartnerContext, require_full_access
from app.db.engine import get_engine
from app.db.repositories import ActivityCategoryRepository
from app.exceptions import NotFoundError
from app.utils import json_response


def handle_partner_activity_categories(
    event: Mapping[str, Any],
    method: str,
    partner: PartnerContext,
    resource_id: str | None,
) -> dict[str, Any]:
    """List the category tree or delete an empty leftover category."""
    require_full_access(partner)
    if method == "GET" and resource_id is None:
        return _list_tree(event)
    if method == "GET" and resource_id:
        return _detail(event, resource_id)
    if method == "DELETE" and resource_id:
        return _delete(event, resource_id)
    return json_response(404, {"error": "Not found"}, event=event)


def _list_tree(event: Mapping[str, Any]) -> dict[str, Any]:
    with Session(get_engine()) as session:
        repo = ActivityCategoryRepository(session)
        tree = _build_activity_category_tree(repo.get_all_flat())
    return json_response(200, {"items": tree}, event=event)


def _detail(event: Mapping[str, Any], raw_id: str) -> dict[str, Any]:
    category_id = _parse_uuid(raw_id)
    with Session(get_engine()) as session:
        repo = ActivityCategoryRepository(session)
        entity = repo.get_by_id(category_id)
        if entity is None:
            raise NotFoundError("activity-categories", raw_id)
        return json_response(
            200,
            _serialize_activity_category(entity),
            event=event,
        )


def _delete(event: Mapping[str, Any], raw_id: str) -> dict[str, Any]:
    category_id = _parse_uuid(raw_id)
    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = ActivityCategoryRepository(session)
        entity = repo.get_by_id(category_id)
        if entity is None:
            raise NotFoundError("activity-categories", raw_id)
        repo.delete(entity)
        session.commit()
    return json_response(204, {}, event=event)
