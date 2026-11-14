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
from app.db.models.category_suggestion import (
    FIXED_ROOT_IDS,
    PENDING_CATEGORY_ID,
    SYSTEM_CATEGORY_ROLES,
)
from app.db.repositories import ActivityCategoryRepository
from app.exceptions import ValidationError
from app.services.activity_categories import (
    create_activity_category,
    parse_display_order,
    parse_hidden_from_public,
    reject_same_parent_name,
    validate_category_parent,
)
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
        "show_in_wizard": bool(entity.show_in_wizard),
        "hidden_from_public": bool(entity.hidden_from_public),
        "is_system": _to_uuid(entity.id) in SYSTEM_CATEGORY_ROLES,
        "system_role": SYSTEM_CATEGORY_ROLES.get(_to_uuid(entity.id)),
    }


def _update_activity_category(
    repo: ActivityCategoryRepository,
    entity: ActivityCategory,
    body: dict[str, Any],
) -> ActivityCategory:
    """Update an activity category."""
    category_id = _to_uuid(entity.id)
    if category_id in SYSTEM_CATEGORY_ROLES and (
        "name" in body or "name_translations" in body or "parent_id" in body
    ):
        raise ValidationError(
            "Pending categorisation cannot be renamed or re-parented"
            if category_id == PENDING_CATEGORY_ID
            else "Fixed root categories cannot be renamed or re-parented",
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
        parent_id = _parse_uuid(parent_id_raw, "parent_id") if parent_id_raw else None
        _validate_category_parent(repo, entity.id, parent_id)
        entity.parent_id = parent_id  # type: ignore[assignment]

    if "display_order" in body:
        entity.display_order = _parse_display_order(body["display_order"])

    if "show_in_wizard" in body:
        show_in_wizard = body["show_in_wizard"]
        if not isinstance(show_in_wizard, bool):
            raise ValidationError(
                "show_in_wizard must be a boolean",
                field="show_in_wizard",
            )
        if show_in_wizard and category_id == PENDING_CATEGORY_ID:
            raise ValidationError(
                "Pending categorisation cannot appear in the home wizard",
                field="show_in_wizard",
            )
        if show_in_wizard and category_id in FIXED_ROOT_IDS:
            raise ValidationError(
                "Fixed root categories cannot appear in the home wizard",
                field="show_in_wizard",
            )
        entity.show_in_wizard = show_in_wizard

    if "hidden_from_public" in body:
        hidden = parse_hidden_from_public(body["hidden_from_public"])
        if category_id == PENDING_CATEGORY_ID:
            raise ValidationError(
                "Pending categorisation is never listed, so it has no "
                "public visibility to change",
                field="hidden_from_public",
            )
        entity.hidden_from_public = hidden

    if "name" in body or "parent_id" in body:
        parent_id = _to_uuid(entity.parent_id) if entity.parent_id else None
        reject_same_parent_name(
            repo,
            str(entity.name),
            parent_id,
            category_id=category_id,
        )

    return entity
