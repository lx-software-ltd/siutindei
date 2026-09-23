"""Activity resource handlers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.range import Range

from app.api.admin_request import _parse_uuid
from app.api.admin_validators import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    _validate_string_length,
    _validate_translations_map,
)
from app.db.age_bounds import inclusive_age_bounds
from app.db.models import Activity
from app.db.repositories import ActivityCategoryRepository, ActivityRepository
from app.exceptions import ValidationError
from app.utils.translations import build_translation_map


def _create_activity(repo: ActivityRepository, body: dict[str, Any]) -> Activity:
    """Create an activity."""
    org_id = body.get("org_id")
    if not org_id:
        raise ValidationError("org_id is required", field="org_id")

    category_id = body.get("category_id")
    if not category_id:
        raise ValidationError("category_id is required", field="category_id")

    name = _validate_string_length(
        body.get("name"), "name", MAX_NAME_LENGTH, required=True
    )
    if name is None:
        raise ValidationError("name is required", field="name")
    _ensure_unique_activity_name(repo, _parse_uuid(org_id), name, current_id=None)
    description = _validate_string_length(
        body.get("description"), "description", MAX_DESCRIPTION_LENGTH
    )
    name_translations = _validate_translations_map(
        body.get("name_translations"), "name_translations", MAX_NAME_LENGTH
    )
    description_translations = _validate_translations_map(
        body.get("description_translations"),
        "description_translations",
        MAX_DESCRIPTION_LENGTH,
    )

    age_min = body.get("age_min")
    age_max = body.get("age_max")
    if age_min is None or age_max is None:
        raise ValidationError("age_min and age_max are required")

    _validate_age_range(age_min, age_max)
    age_range = Range(int(age_min), int(age_max), bounds="[]")

    category_uuid = _parse_uuid(category_id)
    category_repo = ActivityCategoryRepository(repo.session)
    if category_repo.get_by_id(category_uuid) is None:
        raise ValidationError("category_id not found", field="category_id")

    return Activity(
        org_id=_parse_uuid(org_id),
        category_id=category_uuid,
        name=name,
        description=description,
        name_translations=name_translations,
        description_translations=description_translations,
        age_range=age_range,
    )


def _update_activity(
    repo: ActivityRepository,
    entity: Activity,
    body: dict[str, Any],
) -> Activity:
    """Update an activity."""
    if "name" in body:
        name = _validate_string_length(
            body["name"], "name", MAX_NAME_LENGTH, required=True
        )
        if name is None:
            raise ValidationError("name is required", field="name")
        _ensure_unique_activity_name(
            repo, _parse_uuid(str(entity.org_id)), name, current_id=str(entity.id)
        )
        entity.name = name  # type: ignore[assignment]
    if "description" in body:
        entity.description = _validate_string_length(
            body["description"], "description", MAX_DESCRIPTION_LENGTH
        )
    if "name_translations" in body:
        entity.name_translations = _validate_translations_map(
            body["name_translations"], "name_translations", MAX_NAME_LENGTH
        )
    if "description_translations" in body:
        entity.description_translations = _validate_translations_map(
            body["description_translations"],
            "description_translations",
            MAX_DESCRIPTION_LENGTH,
        )
    if "category_id" in body:
        category_id = body["category_id"]
        if not category_id:
            raise ValidationError("category_id is required", field="category_id")
        category_uuid = _parse_uuid(category_id)
        category_repo = ActivityCategoryRepository(repo.session)
        if category_repo.get_by_id(category_uuid) is None:
            raise ValidationError("category_id not found", field="category_id")
        entity.category_id = category_uuid  # type: ignore[assignment]
    if "age_min" in body or "age_max" in body:
        age_min = body.get("age_min")
        age_max = body.get("age_max")
        if age_min is None or age_max is None:
            raise ValidationError("age_min and age_max are required together")
        _validate_age_range(age_min, age_max)
        entity.age_range = Range(int(age_min), int(age_max), bounds="[]")
    return entity


def _validate_age_range(age_min: Any, age_max: Any) -> None:
    """Validate age range values."""
    try:
        age_min_val = int(age_min)
        age_max_val = int(age_max)
    except (ValueError, TypeError) as exc:
        raise ValidationError("age_min and age_max must be valid integers") from exc

    if age_min_val < 0:
        raise ValidationError(
            "age_min must be at least 0",
            field="age_min",
        )
    if age_max_val > 120:
        raise ValidationError(
            "age_max must be at most 120",
            field="age_max",
        )
    if age_min_val >= age_max_val:
        raise ValidationError("age_min must be less than age_max")


def _ensure_unique_activity_name(
    repo: ActivityRepository,
    org_id: str | UUID,
    name: str,
    current_id: str | None,
) -> None:
    """Ensure activity name is unique within an organization."""
    existing = repo.find_by_org_and_name_case_insensitive(
        _parse_uuid(str(org_id)),
        name,
    )
    if existing is None:
        return
    if current_id is not None and str(existing.id) == str(current_id):
        return
    raise ValidationError(
        "Activity name already exists for organization",
        field="name",
    )


def _serialize_activity(entity: Activity) -> dict[str, Any]:
    """Serialize an activity."""
    age_min, age_max = inclusive_age_bounds(entity.age_range)
    return {
        "id": str(entity.id),
        "org_id": str(entity.org_id),
        "category_id": str(entity.category_id),
        "name": entity.name,
        "description": entity.description,
        "name_translations": build_translation_map(
            entity.name, entity.name_translations
        ),
        "description_translations": build_translation_map(
            entity.description, entity.description_translations
        ),
        "age_min": age_min,
        "age_max": age_max,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }
