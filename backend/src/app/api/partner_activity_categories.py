"""Full-access partner read and write for activity categories."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.api.admin_areas import _build_activity_category_tree
from app.api.admin_auth import _set_session_audit_context
from app.api.admin_request import _parse_uuid, parse_object_body
from app.api.admin_resource_activity_category import (
    _serialize_activity_category,
    _update_activity_category,
)
from app.api.partner_auth import (
    PartnerContext,
    partner_actor,
    require_crud,
    require_full_access,
)
from app.db.engine import get_engine
from app.db.repositories import ActivityCategoryRepository
from app.exceptions import NotFoundError, ValidationError
from app.services.activity_categories import create_activity_category
from app.utils import json_response


def handle_partner_activity_categories(
    event: Mapping[str, Any],
    method: str,
    partner: PartnerContext,
    resource_id: str | None,
) -> dict[str, Any]:
    """Read the catalog, or create, update, and delete a category.

    A full-access key can read. Writes require a full-access ``crud`` key.
    """
    require_full_access(partner)
    if method == "GET" and resource_id is None:
        return _list_tree(event)
    if method == "GET" and resource_id:
        return _detail(event, resource_id)
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        require_crud(partner)
    if method == "POST" and resource_id is None:
        return _create(event, partner)
    if method in {"PUT", "PATCH"} and resource_id:
        return _update(event, partner, resource_id)
    if method == "DELETE" and resource_id:
        return _delete(event, partner, resource_id)
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


def _create(event: Mapping[str, Any], partner: PartnerContext) -> dict[str, Any]:
    body = parse_object_body(event)
    _reject_wizard_membership(body)
    with Session(get_engine()) as session:
        _audit(session, event, partner)
        repo = ActivityCategoryRepository(session)
        entity = create_activity_category(repo, body)
        repo.create(entity)
        payload = _serialize_activity_category(entity)
        session.commit()
    return json_response(201, payload, event=event)


def _update(
    event: Mapping[str, Any],
    partner: PartnerContext,
    raw_id: str,
) -> dict[str, Any]:
    category_id = _parse_uuid(raw_id)
    body = parse_object_body(event)
    _reject_wizard_membership(body)
    with Session(get_engine()) as session:
        _audit(session, event, partner)
        repo = ActivityCategoryRepository(session)
        entity = repo.get_by_id(category_id)
        if entity is None:
            raise NotFoundError("activity-categories", raw_id)
        updated = _update_activity_category(repo, entity, body)
        repo.update(updated)
        payload = _serialize_activity_category(updated)
        session.commit()
    return json_response(200, payload, event=event)


def _delete(
    event: Mapping[str, Any],
    partner: PartnerContext,
    raw_id: str,
) -> dict[str, Any]:
    category_id = _parse_uuid(raw_id)
    with Session(get_engine()) as session:
        _audit(session, event, partner)
        repo = ActivityCategoryRepository(session)
        entity = repo.get_by_id(category_id)
        if entity is None:
            raise NotFoundError("activity-categories", raw_id)
        repo.delete(entity)
        session.commit()
    return json_response(204, {}, event=event)


def _audit(session: Session, event: Mapping[str, Any], partner: PartnerContext) -> None:
    _set_session_audit_context(session, event, user_id=partner_actor(event, partner))


def _reject_wizard_membership(body: Mapping[str, Any]) -> None:
    """Home-wizard membership and public visibility are set in the admin console."""
    for field in ("show_in_wizard", "hidden_from_public"):
        if field in body:
            raise ValidationError(
                f"{field} is managed in the admin console",
                field=field,
            )
