"""Geographic areas and activity categories handlers."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sqlalchemy.orm import Session

from app.api.admin_auth import _set_session_audit_context
from app.api.admin_request import _parse_body, _parse_uuid
from app.api.admin_resource_activity_category import _serialize_activity_category
from app.db.engine import get_engine
from app.db.models import ActivityCategory, GeographicArea
from app.db.repositories import ActivityCategoryRepository, GeographicAreaRepository
from app.exceptions import NotFoundError, ValidationError
from app.utils import json_response
from app.utils.translations import build_translation_map


def _handle_list_areas(event: Mapping[str, Any], active_only: bool) -> dict[str, Any]:
    """Return geographic areas (flat or tree)."""
    with Session(get_engine()) as session:
        repo = GeographicAreaRepository(session)
        areas = repo.get_all_flat(active_only=active_only)

    # Build a nested tree from the flat list
    areas_by_id: dict[str, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []

    for area in areas:
        node = _serialize_area(area)
        node["children"] = []
        areas_by_id[str(area.id)] = node

    for area in areas:
        node = areas_by_id[str(area.id)]
        parent_key = str(area.parent_id) if area.parent_id else None
        if parent_key and parent_key in areas_by_id:
            areas_by_id[parent_key]["children"].append(node)
        elif parent_key is None:
            roots.append(node)

    return json_response(200, {"items": roots}, event=event)


def _handle_toggle_area(
    event: Mapping[str, Any],
    area_id_str: str,
) -> dict[str, Any]:
    """Toggle the active flag on a geographic area (admin only)."""
    area_uuid = _parse_uuid(area_id_str)

    body = _parse_body(event)
    active = body.get("active")
    if active is None or not isinstance(active, bool):
        raise ValidationError("active (boolean) is required", field="active")

    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        repo = GeographicAreaRepository(session)
        area = repo.toggle_active(area_uuid, active)
        if area is None:
            raise NotFoundError("geographic_area", area_id_str)
        session.commit()
        session.refresh(area)
        return json_response(200, _serialize_area(area), event=event)


def _serialize_area(area: GeographicArea) -> dict[str, Any]:
    """Serialize a geographic area for the API response."""
    return {
        "id": str(area.id),
        "parent_id": str(area.parent_id) if area.parent_id else None,
        "name": area.name,
        "name_translations": build_translation_map(area.name, area.name_translations),
        "level": area.level,
        "code": area.code,
        "active": area.active,
        "display_order": area.display_order,
        "lat": None if area.lat is None else float(area.lat),
        "lng": None if area.lng is None else float(area.lng),
    }


def _handle_list_activity_categories(
    event: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the activity category tree."""
    with Session(get_engine()) as session:
        repo = ActivityCategoryRepository(session)
        categories = repo.get_all_flat()

    tree = _build_activity_category_tree(categories)
    return json_response(200, {"items": tree}, event=event)


def _build_activity_category_tree(
    categories: Sequence[ActivityCategory],
) -> list[dict[str, Any]]:
    """Build a nested tree from a flat category list."""
    categories_by_id: dict[str, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []

    for category in categories:
        node = _serialize_activity_category(category)
        node["children"] = []
        categories_by_id[str(category.id)] = node

    for category in categories:
        node = categories_by_id[str(category.id)]
        parent_key = str(category.parent_id) if category.parent_id else None
        if parent_key and parent_key in categories_by_id:
            categories_by_id[parent_key]["children"].append(node)
        else:
            roots.append(node)

    _sort_activity_category_tree(roots)
    return roots


def _sort_activity_category_tree(nodes: list[dict[str, Any]]) -> None:
    """Sort category nodes by display_order then name."""
    nodes.sort(key=lambda n: (n["display_order"], n["name"].lower(), n["id"]))
    for node in nodes:
        _sort_activity_category_tree(node["children"])
