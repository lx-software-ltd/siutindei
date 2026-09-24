"""Activity category resource handlers."""

from __future__ import annotations

from typing import Any

from app.api.admin_request import _parse_uuid, _to_uuid
from app.api.admin_validators import (
    MAX_NAME_LENGTH,
    _validate_string_length,
    _validate_translations_map,
)
from app.db.models import ActivityCategory
from app.db.models.category_suggestion import PENDING_CATEGORY_ID
from app.db.repositories import ActivityCategoryRepository
from app.exceptions import ValidationError
from app.services.activity_categories import create_activity_category
from app.services.activity_categories import parse_display_order
from app.services.activity_categories import validate_category_parent
from app.utils.translations import build_translation_map

_create_activity_category = create_activity_category
_parse_display_order = parse_display_order
_validate_category_parent = validate_category_parent


def _serialize_activity_category(entity: ActivityCategory) -> dict[str, Any]:
    """Serialize an activity category."""
    return {
        "id": str(entity.id),
        "parent_id": str(entity.parent_id) if entity.parent_id else None,
        "name": entity.name,
        "name_translations": build_translation_map(
            entity.name, entity.name_translations
        ),
        "display_order": entity.display_order,
        "is_system": _to_uuid(entity.id) == PENDING_CATEGORY_ID,
    }


def _update_activity_category(
    repo: ActivityCategoryRepository,
    entity: ActivityCategory,
    body: dict[str, Any],
) -> ActivityCategory:
    """Update an activity category."""
    if _to_uuid(entity.id) == PENDING_CATEGORY_ID and (
        "name" in body or "name_translations" in body or "parent_id" in body
    ):
        raise ValidationError(
            "Pending categorisation cannot be renamed or re-parented",
            field="id",
        )
    if "name" in body:
        name = _validate_string_length(
            body["name"], "name", MAX_NAME_LENGTH, required=True
        )
        entity.name = name  # type: ignore[assignment]
    if "name_translations" in body:
        entity.name_translations = _validate_translations_map(
            body["name_translations"], "name_translations", MAX_NAME_LENGTH
        )

    if "parent_id" in body:
        parent_id_raw = body["parent_id"]
        parent_id = _parse_uuid(parent_id_raw) if parent_id_raw else None
        _validate_category_parent(repo, entity.id, parent_id)
        entity.parent_id = parent_id  # type: ignore[assignment]

    if "display_order" in body:
        entity.display_order = _parse_display_order(body["display_order"])

    return entity
