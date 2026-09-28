"""Activity category construction shared by admin APIs and decisions."""

from __future__ import annotations

from typing import Any
from typing import Optional
from uuid import UUID

from app.api.admin_request import _parse_uuid
from app.api.admin_validators import (
    MAX_NAME_LENGTH,
    _validate_string_length,
    _validate_translations_map,
)
from app.db.models import ActivityCategory
from app.db.models.category_suggestion import PENDING_CATEGORY_ID
from app.db.repositories import ActivityCategoryRepository
from app.exceptions import ValidationError


def parse_display_order(value: Any) -> int:
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


def validate_category_parent(
    repo: ActivityCategoryRepository,
    category_id: Optional[UUID | str],
    parent_id: Optional[UUID],
) -> None:
    """Validate that a parent exists and does not create cycles."""
    category_uuid = _as_uuid(category_id) if category_id is not None else None
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


def create_activity_category(
    repo: ActivityCategoryRepository,
    body: dict[str, Any],
) -> ActivityCategory:
    """Build a new category from an admin payload. The caller flushes it."""
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
    validate_category_parent(repo, None, parent_id)
    display_order = parse_display_order(body.get("display_order"))

    return ActivityCategory(
        name=name,
        name_translations=name_translations,
        parent_id=parent_id,
        display_order=display_order,
    )


def _as_uuid(value: UUID | str) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
