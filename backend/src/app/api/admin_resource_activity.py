"""Activity resource handlers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.range import Range
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.api.admin_imports_catalog import (
    MAX_VETTING_NOTE_LENGTH,
    MAX_WEBSITE_LENGTH,
)
from app.api.admin_request import _parse_uuid
from app.api.admin_validators import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    _validate_string_length,
    _validate_translations_map,
)
from app.db.age_bounds import inclusive_age_bounds
from app.db.models import (
    Activity,
    ActivityLocation,
    ActivityPricing,
    ActivitySchedule,
    Location,
)
from app.db.repositories import ActivityCategoryRepository, ActivityRepository
from app.exceptions import ValidationError
from app.services.listing_kinds import (
    DEFAULT_KIND,
    assign_category,
    facts_for_kind,
    kind_for_category,
    parse_kind,
    validate_facts,
)
from app.services.org_review_decision import reject_if_only_hidden
from app.utils.translations import build_translation_map

MAX_ACTIVITY_LOCATIONS = 100


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

    kind = parse_kind(body["kind"]) if "kind" in body else DEFAULT_KIND
    facts = validate_facts(kind, body.get("facts"))
    kind = kind_for_category(repo.session, category_uuid, kind)
    facts = facts_for_kind(kind, facts)

    location_ids = _optional_location_ids(body)
    parsed_org_id = _parse_uuid(org_id)
    if location_ids is not None:
        _assert_locations_for_org(repo.session, parsed_org_id, location_ids)

    entity = Activity(
        org_id=parsed_org_id,
        category_id=category_uuid,
        name=name,
        description=description,
        name_translations=name_translations,
        description_translations=description_translations,
        source_url=_validate_string_length(
            body.get("source_url"),
            "source_url",
            MAX_WEBSITE_LENGTH,
        ),
        source_note=_validate_string_length(
            body.get("source_note"),
            "source_note",
            MAX_VETTING_NOTE_LENGTH,
        ),
        source_category_name=_source_category_name(body.get("source_category_name")),
        age_range=age_range,
        kind=kind,
        facts=facts,
    )
    from app.services.data_quality.names import record_imported_name

    record_imported_name(repo.session, entity, body, "activity")
    if location_ids:
        repo.session.add(entity)
        repo.session.flush()
        _set_activity_locations(entity, location_ids)
    return entity


def _update_activity_for_manager(
    repo: ActivityRepository,
    entity: Activity,
    body: dict[str, Any],
) -> Activity:
    """Update an activity for a manager (no provenance, kind, or facts)."""
    body.pop("source_url", None)
    body.pop("source_note", None)
    body.pop("source_category_name", None)
    body.pop("kind", None)
    body.pop("facts", None)
    return _update_activity(repo, entity, body)


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
    if "source_url" in body:
        entity.source_url = _validate_string_length(
            body["source_url"],
            "source_url",
            MAX_WEBSITE_LENGTH,
        )
    if "source_note" in body:
        entity.source_note = _validate_string_length(
            body["source_note"],
            "source_note",
            MAX_VETTING_NOTE_LENGTH,
        )
    if "source_category_name" in body:
        entity.source_category_name = _source_category_name(
            body.get("source_category_name")
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
    if "kind" in body or "facts" in body:
        _apply_kind_and_facts(entity, body)
    if "category_id" in body or "kind" in body:
        assign_category(repo.session, entity, entity.category_id)
    if "location_ids" in body:
        location_ids = _parse_location_ids(body["location_ids"])
        _assert_locations_for_org(repo.session, entity.org_id, location_ids)
        _replace_activity_locations(repo.session, entity, location_ids)
    from app.services.data_quality.names import record_imported_name

    record_imported_name(repo.session, entity, body, "activity")
    return entity


def _after_activity_write(session: Session, entity: Activity) -> None:
    """A category change can leave the organization with only hidden ones."""
    reject_if_only_hidden(session, entity.org_id)


def _apply_kind_and_facts(entity: Activity, body: dict[str, Any]) -> None:
    """Set kind and facts. A new kind drops the facts it does not allow."""
    kind = parse_kind(body["kind"]) if "kind" in body else entity.kind
    if "facts" in body:
        entity.facts = validate_facts(kind, body["facts"])
    else:
        entity.facts = facts_for_kind(kind, entity.facts)
    entity.kind = kind


def _source_category_name(value: Any) -> str | None:
    """Keep a non-empty imported category label."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


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
        "source_url": entity.source_url,
        "source_note": entity.source_note,
        "source_category_name": entity.source_category_name,
        "age_min": age_min,
        "age_max": age_max,
        "kind": entity.kind,
        "facts": entity.facts or {},
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
        "version": entity.version,
        "location_ids": _activity_location_ids(entity),
    }


def _optional_location_ids(body: dict[str, Any]) -> list[UUID] | None:
    if "location_ids" not in body:
        return None
    return _parse_location_ids(body["location_ids"])


def _parse_location_ids(raw: Any) -> list[UUID]:
    if not isinstance(raw, list):
        raise ValidationError("location_ids must be a list", field="location_ids")
    if len(raw) > MAX_ACTIVITY_LOCATIONS:
        raise ValidationError("location_ids is too long", field="location_ids")
    parsed: list[UUID] = []
    seen: set[str] = set()
    for item in raw:
        location_id = _parse_uuid(item, field="location_ids")
        key = str(location_id)
        if key in seen:
            continue
        seen.add(key)
        parsed.append(location_id)
    return parsed


def _assert_locations_for_org(
    session: Session,
    org_id: UUID | str,
    location_ids: list[UUID],
) -> None:
    if not location_ids:
        return
    rows = session.scalars(select(Location).where(Location.id.in_(location_ids))).all()
    found = {str(row.id): row for row in rows}
    org_key = str(org_id)
    for location_id in location_ids:
        row = found.get(str(location_id))
        if row is None:
            raise ValidationError("location_ids not found", field="location_ids")
        if str(row.org_id) != org_key:
            raise ValidationError(
                "location_ids must belong to this organization",
                field="location_ids",
            )


def _replace_activity_locations(
    session: Session,
    entity: Activity,
    location_ids: list[UUID],
) -> None:
    current = list(
        session.scalars(
            select(ActivityLocation).where(ActivityLocation.activity_id == entity.id)
        ).all()
    )
    current_ids = {str(row.location_id) for row in current}
    removed = current_ids - {str(item) for item in location_ids}
    added = [item for item in location_ids if str(item) not in current_ids]
    if removed:
        _reject_venues_in_use(session, entity.id, removed)
    if not removed and not added:
        return
    for row in current:
        if str(row.location_id) in removed:
            session.delete(row)
    if removed:
        session.flush()
    _set_activity_locations(entity, added)
    session.expire(entity, ["locations"])


def _reject_venues_in_use(
    session: Session,
    activity_id: UUID | str,
    removed: set[str],
) -> None:
    removed_ids = [UUID(item) for item in removed]
    priced = session.scalar(
        select(ActivityPricing.id)
        .where(
            ActivityPricing.activity_id == activity_id,
            ActivityPricing.location_id.in_(removed_ids),
        )
        .limit(1)
    )
    scheduled = session.scalar(
        select(ActivitySchedule.id)
        .where(
            ActivitySchedule.activity_id == activity_id,
            ActivitySchedule.location_id.in_(removed_ids),
        )
        .limit(1)
    )
    if priced is not None or scheduled is not None:
        raise ValidationError(
            "location_ids still used by pricing or schedules",
            field="location_ids",
        )


def _set_activity_locations(entity: Activity, location_ids: list[UUID]) -> None:
    for location_id in location_ids:
        entity.locations.append(
            ActivityLocation(activity_id=entity.id, location_id=location_id)
        )


def _activity_location_ids(entity: Activity) -> list[str]:
    loaded = entity.__dict__.get("locations")
    if loaded is not None:
        return sorted(str(link.location_id) for link in loaded)
    session = object_session(entity)
    if session is None:
        return []
    rows = session.scalars(
        select(ActivityLocation.location_id)
        .where(ActivityLocation.activity_id == entity.id)
        .order_by(ActivityLocation.location_id)
    ).all()
    return [str(row) for row in rows]
