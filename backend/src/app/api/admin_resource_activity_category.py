"""Activity category resource handlers."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

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
from app.utils.translations import build_translation_map


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


def _parse_display_order(value: Any) -> int:
    """Parse and validate display_order."""
    if value is None:
        return 0
    try:
        parsed = int(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "display_order must be a valid integer",
            field="display_order",
        ) from exc
    if parsed < 0:
        raise ValidationError(
            "display_order must be at least 0",
            field="display_order",
        )
    return parsed


def _validate_category_parent(
    repo: ActivityCategoryRepository,
    category_id: Optional[UUID | str],
    parent_id: Optional[UUID],
) -> None:
    """Validate that a parent exists and does not create cycles."""
    category_uuid = _to_uuid(category_id) if category_id is not None else None
    if parent_id is None:
        return
    if parent_id == PENDING_CATEGORY_ID:
        raise ValidationError(
            "Pending categorisation cannot be a parent",
            field="parent_id",
        )
    if category_uuid is not None and parent_id == category_uuid:
        raise ValidationError(
            "parent_id cannot reference the same category",
            field="parent_id",
        )

    if repo.get_by_id(parent_id) is None:
        raise ValidationError("parent_id not found", field="parent_id")

    if category_uuid is None:
        return

    categories = repo.get_all_flat()
    children_by_parent: dict[str, list[str]] = {}
    for category in categories:
        if category.parent_id is None:
            continue
        pid = str(category.parent_id)
        children_by_parent.setdefault(pid, []).append(str(category.id))

    stack = [str(category_uuid)]
    descendants: set[str] = set()
    while stack:
        current = stack.pop()
        for child_id in children_by_parent.get(current, []):
            if child_id in descendants:
                continue
            descendants.add(child_id)
            stack.append(child_id)

    if str(parent_id) in descendants:
        raise ValidationError(
            "parent_id cannot be a descendant category",
            field="parent_id",
        )


def _create_activity_category(
    repo: ActivityCategoryRepository,
    body: dict[str, Any],
) -> ActivityCategory:
    """Create an activity category."""
    name = _validate_string_length(
        body.get("name"),
        "name",
        MAX_NAME_LENGTH,
        required=True,
    )
    name_translations = _validate_translations_map(
        body.get("name_translations"), "name_translations", MAX_NAME_LENGTH
    )
    parent_id_raw = body.get("parent_id")
    parent_id = _parse_uuid(parent_id_raw) if parent_id_raw else None
    _validate_category_parent(repo, None, parent_id)
    display_order = _parse_display_order(body.get("display_order"))

    return ActivityCategory(
        name=name,
        name_translations=name_translations,
        parent_id=parent_id,
        display_order=display_order,
    )


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
