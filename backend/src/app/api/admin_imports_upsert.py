"""Upsert helpers for admin imports."""

from __future__ import annotations

from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session

from app.api.admin_imports_fields import (
    guard_import_organization_update,
    manager_ids_match,
)
from app.api.admin_imports_venues import (
    LINKED_VENUE_WARNING,
    link_activity_to_venue,
)
from app.api.admin_imports_utils import (
    collect_unknown_fields,
    parse_day_of_week,
    parse_time_minutes,
    parse_timezone,
    persist_import_change,
    to_utc_weekly,
)
from app.api.admin_resource_activity import _create_activity, _update_activity
from app.api.admin_resource_location import _create_location, _update_location
from app.api.admin_resource_organization import (
    _create_organization,
    _update_organization,
)
from app.api.admin_resource_pricing import _create_pricing, _update_pricing
from app.api.admin_resource_schedule import _create_schedule, _update_schedule
from app.api.admin_validators import (
    MAX_NAME_LENGTH,
    _parse_languages,
    _validate_string_length,
)
from app.db.models import Activity, ActivityCategory
from app.db.models import ActivityPricing, ActivitySchedule
from app.db.models import GeographicArea, Location, Organization, PricingType
from app.db.repositories import (
    ActivityPricingRepository,
    ActivityRepository,
    ActivityScheduleRepository,
    LocationRepository,
    OrganizationRepository,
)
from app.exceptions import ValidationError

ALLOWED_ORG_FIELDS = {
    "name",
    "description",
    "name_translations",
    "description_translations",
    "manager_id",
    "phone_country_code",
    "phone_number",
    "email",
    "whatsapp",
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "xiaohongshu",
    "wechat",
    "media_urls",
    "logo_media_url",
    "locations",
    "activities",
    "source_url",
    "vetting_note",
    "area_name",
    "category_name",
    "address",
    "lat",
    "lng",
    "website",
    "phone",
}
ALLOWED_LOCATION_FIELDS = {
    "name",
    "address",
    "area_id",
    "area_name",
    "lat",
    "lng",
}
ALLOWED_ACTIVITY_FIELDS = {
    "name",
    "description",
    "name_translations",
    "description_translations",
    "age_min",
    "age_max",
    "category_id",
    "category_name",
    "source_url",
    "vetting_note",
    "pricing",
    "schedules",
}
ALLOWED_PRICING_FIELDS = {
    "location_name",
    "pricing_type",
    "amount",
    "currency",
    "sessions_count",
    "free_trial_class_offered",
}
ALLOWED_SCHEDULE_FIELDS = {
    "location_name",
    "timezone",
    "languages",
    "weekly_entries",
}
ALLOWED_ENTRY_FIELDS = {"day_of_week", "start_time", "end_time"}


def upsert_organization(
    session: Session,
    raw_org: dict[str, Any],
    *,
    dry_run: bool = False,
    allow_updates: bool = False,
) -> tuple[Organization, str]:
    repo = OrganizationRepository(session)
    name = _validate_string_length(
        raw_org.get("name"),
        "name",
        MAX_NAME_LENGTH,
        required=True,
    )
    if name is None:
        raise ValidationError("name is required", field="name")
    try:
        existing = repo.find_by_name_case_insensitive(name)
    except MultipleResultsFound as exc:
        raise ValidationError(
            "Multiple organizations found",
            field="name",
        ) from exc

    body = _filter_fields(raw_org, ALLOWED_ORG_FIELDS)
    for extra in (
        "locations",
        "activities",
        "source_url",
        "vetting_note",
        "area_name",
        "category_name",
        "address",
        "lat",
        "lng",
        "website",
        "phone",
    ):
        body.pop(extra, None)
    if existing:
        if not allow_updates:
            if manager_ids_match(existing.manager_id, body.get("manager_id")):
                return existing, "skipped"
            raise ValidationError("exists", field="name")
        guard_import_organization_update(existing, body)
        updated = _update_organization(repo, existing, body)
        repo.update(updated)
        persist_import_change(session, dry_run=dry_run)
        session.refresh(updated)
        return updated, "updated"

    if not raw_org.get("manager_id"):
        raise ValidationError("manager_id is required", field="manager_id")
    created = _create_organization(repo, body)
    repo.create(created)
    persist_import_change(session, dry_run=dry_run)
    session.refresh(created)
    return created, "created"


def upsert_location(
    session: Session,
    org: Organization,
    raw_location: dict[str, Any],
    address_value: str,
    *,
    dry_run: bool = False,
    allow_updates: bool = True,
) -> tuple[Location, str]:
    repo = LocationRepository(session)
    try:
        existing = repo.find_by_org_and_address_case_insensitive(
            _coerce_uuid(org.id),
            address_value,
        )
    except MultipleResultsFound as exc:
        raise ValidationError("Multiple locations found", field="name") from exc

    if existing and not allow_updates:
        return existing, "skipped"

    body = _filter_fields(raw_location, ALLOWED_LOCATION_FIELDS)
    _resolve_location_area_fields(session, body)
    if raw_location.get("name") is not None or raw_location.get("address") is not None:
        body["address"] = address_value
    if existing:
        updated = _update_location(repo, existing, body)
        repo.update(updated)
        persist_import_change(session, dry_run=dry_run)
        session.refresh(updated)
        return updated, "updated"

    body["org_id"] = str(org.id)
    body["address"] = address_value
    created = _create_location(repo, body)
    repo.create(created)
    persist_import_change(session, dry_run=dry_run)
    session.refresh(created)
    return created, "created"


def upsert_activity(
    session: Session,
    org: Organization,
    raw_activity: dict[str, Any],
    *,
    dry_run: bool = False,
    allow_updates: bool = True,
    venue: Location | None = None,
    warnings: list[str] | None = None,
) -> tuple[Activity, str]:
    repo = ActivityRepository(session)
    name = _validate_string_length(
        raw_activity.get("name"),
        "name",
        MAX_NAME_LENGTH,
        required=True,
    )
    if name is None:
        raise ValidationError("name is required", field="name")
    try:
        existing = repo.find_by_org_and_name_case_insensitive(
            _coerce_uuid(org.id), name
        )
    except MultipleResultsFound as exc:
        raise ValidationError(
            "Multiple activities found",
            field="name",
        ) from exc

    if existing and not allow_updates:
        wrote_link = link_activity_to_venue(session, existing, venue)
        if wrote_link:
            if warnings is not None:
                warnings.append(LINKED_VENUE_WARNING)
            persist_import_change(session, dry_run=dry_run)
        return existing, "skipped"

    body = _filter_fields(raw_activity, ALLOWED_ACTIVITY_FIELDS)
    _resolve_activity_category_fields(session, body)
    body.pop("pricing", None)
    body.pop("schedules", None)
    body.pop("source_url", None)
    body.pop("vetting_note", None)
    if existing:
        updated = _update_activity(repo, existing, body)
        repo.update(updated)
        link_activity_to_venue(session, updated, venue)
        persist_import_change(session, dry_run=dry_run)
        session.refresh(updated)
        return updated, "updated"

    body["org_id"] = str(org.id)
    created = _create_activity(repo, body)
    repo.create(created)
    link_activity_to_venue(session, created, venue)
    persist_import_change(session, dry_run=dry_run)
    session.refresh(created)
    return created, "created"


def upsert_pricing(
    session: Session,
    activity: Activity,
    location: Location,
    raw_pricing: dict[str, Any],
    *,
    dry_run: bool = False,
    allow_updates: bool = True,
) -> tuple[ActivityPricing, str]:
    pricing_type = raw_pricing.get("pricing_type")
    if not pricing_type:
        raise ValidationError("pricing_type is required", field="pricing_type")
    try:
        pricing_enum = PricingType(str(pricing_type))
    except ValueError as exc:
        raise ValidationError(
            "Invalid pricing_type",
            field="pricing_type",
        ) from exc

    repo = ActivityPricingRepository(session)
    try:
        existing = repo.find_by_activity_location_pricing_type(
            _coerce_uuid(activity.id),
            _coerce_uuid(location.id),
            pricing_enum,
        )
    except MultipleResultsFound as exc:
        raise ValidationError(
            "Multiple pricing entries found",
            field="pricing_type",
        ) from exc

    if existing and not allow_updates:
        return existing, "skipped"

    body = _filter_fields(raw_pricing, ALLOWED_PRICING_FIELDS)
    body["pricing_type"] = pricing_enum.value
    if existing:
        updated = _update_pricing(repo, existing, body)
        repo.update(updated)
        persist_import_change(session, dry_run=dry_run)
        session.refresh(updated)
        return updated, "updated"

    body["activity_id"] = str(activity.id)
    body["location_id"] = str(location.id)
    created = _create_pricing(repo, body)
    repo.create(created)
    persist_import_change(session, dry_run=dry_run)
    session.refresh(created)
    return created, "created"


def upsert_schedule(
    session: Session,
    activity: Activity,
    location: Location,
    raw_schedule: dict[str, Any],
    warnings: list[str],
    *,
    dry_run: bool = False,
    allow_updates: bool = True,
) -> tuple[ActivitySchedule, str]:
    tzinfo = parse_timezone(raw_schedule.get("timezone"), "timezone")
    languages = _parse_languages(raw_schedule.get("languages"))
    repo = ActivityScheduleRepository(session)
    existing = repo.find_by_activity_location_languages(
        _coerce_uuid(activity.id),
        _coerce_uuid(location.id),
        languages,
    )
    if existing and not allow_updates:
        return existing, "skipped"

    entries = parse_weekly_entries_local(
        raw_schedule.get("weekly_entries"),
        tzinfo,
        warnings,
    )
    if not entries:
        raise ValidationError(
            "weekly_entries must include at least one entry",
            field="weekly_entries",
        )

    body = {
        "activity_id": str(activity.id),
        "location_id": str(location.id),
        "schedule_type": "weekly",
        "languages": languages,
        "weekly_entries": entries,
    }
    if existing:
        body["weekly_entries"] = merge_schedule_entries(existing, entries)
        updated = _update_schedule(repo, existing, body)
        repo.update(updated)
        persist_import_change(session, dry_run=dry_run)
        session.refresh(updated)
        return updated, "updated"

    created = _create_schedule(repo, body)
    repo.create(created)
    persist_import_change(session, dry_run=dry_run)
    session.refresh(created)
    return created, "created"


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


def resolve_location(
    session: Session,
    org: Organization,
    location_name: str,
    cache: dict[str, Location],
) -> Location | None:
    cached = cache.get(location_name)
    if cached:
        return cached
    repo = LocationRepository(session)
    try:
        location = repo.find_by_org_and_address_case_insensitive(
            _coerce_uuid(org.id),
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


def _resolve_location_area_fields(
    session: Session,
    body: dict[str, Any],
) -> None:
    area_name = body.pop("area_name", None)
    if body.get("area_id") is not None:
        return
    if area_name is None:
        return
    body["area_id"] = _lookup_district_area_id(session, area_name)


def _resolve_activity_category_fields(
    session: Session,
    body: dict[str, Any],
) -> None:
    category_name = body.pop("category_name", None)
    if body.get("category_id") is not None:
        return
    if category_name is None:
        return
    body["category_id"] = _lookup_category_id(session, category_name)


def _lookup_district_area_id(session: Session, area_name: Any) -> str:
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


def _lookup_category_id(session: Session, category_name: Any) -> str:
    if not isinstance(category_name, str) or not category_name:
        raise ValidationError("unknown category_name", field="category_name")
    query = (
        select(ActivityCategory.id)
        .where(
            ActivityCategory.name == category_name,
        )
        .limit(2)
    )
    matches = session.execute(query).scalars().all()
    if len(matches) != 1:
        raise ValidationError("unknown category_name", field="category_name")
    return str(matches[0])


def _filter_fields(
    payload: dict[str, Any],
    allowed: set[str],
) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key in allowed}


def _coerce_uuid(value: str | UUID) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
