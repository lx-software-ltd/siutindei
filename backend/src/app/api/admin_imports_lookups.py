"""Name/category lookups and listing-body helpers for imports."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import (
    MANAGED_BY_PROVIDER,
    coerce_uuid,
    parse_description_source,
    parse_place_id,
)
from app.api.admin_imports_fields import manager_ids_match
from app.api.admin_imports_utils import (
    collect_unknown_fields,
    parse_day_of_week,
    parse_time_minutes,
    to_utc_weekly,
)
from app.db.models import ActivityCategory, ActivitySchedule, GeographicArea
from app.db.models import Location, Organization
from app.db.repositories import LocationRepository
from app.exceptions import ValidationError

ALLOWED_ENTRY_FIELDS = {"day_of_week", "start_time", "end_time"}


def prepare_listing_body(body: dict[str, Any]) -> None:
    """Normalize catalog listing fields on an org upsert body."""
    if "place_id" in body:
        body["place_id"] = parse_place_id(body.get("place_id"))
    if "description_source" in body:
        body["description_source"] = parse_description_source(
            body.get("description_source")
        )
    if "source_id" in body and body["source_id"] is not None:
        body["source_id"] = str(body["source_id"]).strip() or None
    if "source" in body and body["source"] is not None:
        body["source"] = str(body["source"]).strip() or None
    body.pop("status", None)


def guard_existing_org(
    existing: Organization,
    body: dict[str, Any],
    *,
    allow_updates: bool,
    catalog_manager_id: str | None,
) -> None:
    """Skip or fail when the match is owned by another manager."""
    payload_manager = body.get("manager_id")
    if catalog_manager_id and not manager_ids_match(
        existing.manager_id,
        catalog_manager_id,
    ):
        raise ValidationError(MANAGED_BY_PROVIDER, field="manager_id")
    if allow_updates:
        return
    if not manager_ids_match(existing.manager_id, payload_manager):
        raise ValidationError("exists", field="name")


def resolve_location_area_fields(
    session: Session,
    body: dict[str, Any],
) -> None:
    area_name = body.pop("area_name", None)
    if body.get("area_id") is not None:
        return
    if area_name is None:
        return
    body["area_id"] = lookup_district_area_id(session, area_name)


def resolve_activity_category_fields(
    session: Session,
    body: dict[str, Any],
) -> None:
    category_name = body.pop("category_name", None)
    if body.get("category_id") is not None:
        return
    if category_name is None:
        return
    from app.db.models.category_suggestion import PENDING_CATEGORY_ID
    from app.services.category_suggestions.capture import ensure_pending_category
    from app.services.category_suggestions.resolve import resolve_category_name

    resolution = resolve_category_name(session, str(category_name))
    if resolution.capture:
        ensure_pending_category(session)
        body["category_id"] = str(PENDING_CATEGORY_ID)
        body["_capture_category_name"] = str(category_name).strip()
        return
    if resolution.category_id is None:
        raise ValidationError("unknown category_name", field="category_name")
    body["category_id"] = str(resolution.category_id)


def lookup_district_area_id(session: Session, area_name: Any) -> str:
    if not isinstance(area_name, str) or not area_name:
        raise ValidationError("unknown area_name", field="area_name")
    query = (
        select(GeographicArea.id)
        .where(GeographicArea.name == area_name)
        .where(GeographicArea.level == "district")
        .limit(2)
    )
    matches = session.execute(query).scalars().all()
    if len(matches) != 1:
        raise ValidationError("unknown area_name", field="area_name")
    return str(matches[0])


def lookup_category_id(session: Session, category_name: Any) -> str:
    if not isinstance(category_name, str) or not category_name:
        raise ValidationError("unknown category_name", field="category_name")
    query = (
        select(ActivityCategory.id)
        .where(ActivityCategory.name == category_name)
        .limit(2)
    )
    matches = session.execute(query).scalars().all()
    if len(matches) != 1:
        raise ValidationError("unknown category_name", field="category_name")
    return str(matches[0])


def filter_fields(
    payload: dict[str, Any],
    allowed: set[str],
) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key in allowed}


def merge_schedule_entries(
    schedule: ActivitySchedule,
    new_entries: list[dict[str, int]],
) -> list[dict[str, int]]:
    seen: set[tuple[int, int, int]] = set()
    merged: list[dict[str, int]] = []

    for existing_entry in schedule.entries or []:
        key = (
            existing_entry.day_of_week_utc,
            existing_entry.start_minutes_utc,
            existing_entry.end_minutes_utc,
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                "day_of_week_utc": existing_entry.day_of_week_utc,
                "start_minutes_utc": existing_entry.start_minutes_utc,
                "end_minutes_utc": existing_entry.end_minutes_utc,
            }
        )

    for new_entry in new_entries:
        key = (
            new_entry["day_of_week_utc"],
            new_entry["start_minutes_utc"],
            new_entry["end_minutes_utc"],
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(new_entry)

    merged.sort(
        key=lambda item: (
            item["day_of_week_utc"],
            item["start_minutes_utc"],
            item["end_minutes_utc"],
        )
    )
    return merged


def parse_weekly_entries_local(
    value: Any,
    tzinfo: ZoneInfo,
    warnings: list[str],
) -> list[dict[str, int]]:
    if value is None:
        raise ValidationError(
            "weekly_entries is required",
            field="weekly_entries",
        )
    if not isinstance(value, list):
        raise ValidationError(
            "weekly_entries must be a list",
            field="weekly_entries",
        )
    if not value:
        return []

    entries: list[dict[str, int]] = []
    seen: set[tuple[int, int, int]] = set()

    for index, raw in enumerate(value):
        field_prefix = f"weekly_entries[{index}]"
        if not isinstance(raw, dict):
            raise ValidationError(
                "weekly_entries must be objects",
                field=field_prefix,
            )
        collect_unknown_fields(
            raw,
            ALLOWED_ENTRY_FIELDS,
            field_prefix,
            warnings,
        )
        day_of_week = parse_day_of_week(
            raw.get("day_of_week"),
            f"{field_prefix}.day_of_week",
        )
        start_minutes = parse_time_minutes(
            raw.get("start_time"),
            f"{field_prefix}.start_time",
        )
        end_minutes = parse_time_minutes(
            raw.get("end_time"),
            f"{field_prefix}.end_time",
        )
        if start_minutes == end_minutes:
            raise ValidationError(
                "start_time must not equal end_time",
                field=f"{field_prefix}.start_time",
            )

        day_utc, start_utc, end_utc = to_utc_weekly(
            day_of_week,
            start_minutes,
            end_minutes,
            tzinfo,
        )
        key = (day_utc, start_utc, end_utc)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "day_of_week_utc": day_utc,
                "start_minutes_utc": start_utc,
                "end_minutes_utc": end_utc,
            }
        )

    return entries


def resolve_location(
    session: Session,
    org: Organization,
    location_name: str,
    cache: dict[str, Location],
) -> Location | None:
    """Find a location by the import location_name cache, then address."""
    cached = cache.get(location_name)
    if cached:
        return cached
    repo = LocationRepository(session)
    try:
        location = repo.find_by_org_and_address_case_insensitive(
            coerce_uuid(org.id),
            location_name,
        )
    except MultipleResultsFound as exc:
        raise ValidationError(
            "Multiple locations found for name",
            field="location_name",
        ) from exc
    if location:
        cache[location_name] = location
    return location
