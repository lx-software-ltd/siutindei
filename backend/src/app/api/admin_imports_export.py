"""Export helpers for admin import/export."""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session

from app.api.admin_imports_utils import (
    format_minutes,
    from_utc_weekly,
    parse_timezone,
    sanitize_filename,
)
from app.db.models import Activity, ActivityPricing, ActivitySchedule, Location
from app.db.models import Organization
from app.db.repositories import OrganizationRepository
from app.exceptions import ValidationError


def load_export_organizations(
    session: Session,
    org_name: str | None,
) -> list[Organization]:
    repo = OrganizationRepository(session)
    if org_name:
        try:
            org = repo.find_by_name(org_name)
        except MultipleResultsFound as exc:
            raise ValidationError(
                "Multiple organizations found for name",
                field="org_name",
            ) from exc
        if org is None:
            raise ValidationError("org_name not found", field="org_name")
        return [org]

    query = select(Organization).order_by(Organization.name, Organization.id)
    return list(session.execute(query).scalars().all())


def build_export_payload(
    session: Session,
    organizations: list[Organization],
    timezone_name: str,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    tzinfo = parse_timezone(timezone_name, field_name="timezone")
    org_payloads: list[dict[str, Any]] = []

    for org in organizations:
        locations = list(
            session.execute(
                select(Location).where(Location.org_id == org.id).order_by(Location.id)
            )
            .scalars()
            .all()
        )
        activities = list(
            session.execute(
                select(Activity).where(Activity.org_id == org.id).order_by(Activity.id)
            )
            .scalars()
            .all()
        )
        pricing_rows = list(
            session.execute(
                select(ActivityPricing)
                .join(Activity, ActivityPricing.activity_id == Activity.id)
                .where(Activity.org_id == org.id)
                .order_by(ActivityPricing.id)
            )
            .scalars()
            .all()
        )
        schedule_rows = list(
            session.execute(
                select(ActivitySchedule)
                .join(Activity, ActivitySchedule.activity_id == Activity.id)
                .where(Activity.org_id == org.id)
                .order_by(ActivitySchedule.id)
            )
            .scalars()
            .all()
        )
        location_name_by_id = build_location_name_map(locations, warnings)
        org_payloads.append(
            serialize_export_organization(
                org,
                locations,
                activities,
                pricing_rows,
                schedule_rows,
                location_name_by_id,
                tzinfo,
                warnings,
            )
        )

    return {"organizations": org_payloads}, warnings


def export_file_name(org_name: str | None) -> str:
    if not org_name:
        return "admin-export.json"
    cleaned = sanitize_filename(org_name)
    base, _ = os.path.splitext(cleaned)
    trimmed_base = base[:40].strip("_") or "organization"
    return f"{trimmed_base}-export.json"


def build_location_name_map(
    locations: list[Location],
    warnings: list[str],
) -> dict[str, str]:
    name_by_id: dict[str, str] = {}
    for location in locations:
        loc_id = str(location.id)
        if location.address:
            name_by_id[loc_id] = location.address
            continue
        fallback = f"location-{loc_id}"
        warnings.append(f"Location {loc_id} has no address; using {fallback} as name.")
        name_by_id[loc_id] = fallback
    return name_by_id


def serialize_export_organization(
    org: Organization,
    locations: list[Location],
    activities: list[Activity],
    pricing_rows: list[ActivityPricing],
    schedule_rows: list[ActivitySchedule],
    location_name_by_id: dict[str, str],
    tzinfo: ZoneInfo,
    warnings: list[str],
) -> dict[str, Any]:
    pricing_by_activity: dict[str, list[ActivityPricing]] = {}
    for pricing in pricing_rows:
        pricing_by_activity.setdefault(str(pricing.activity_id), []).append(pricing)

    schedules_by_activity: dict[str, list[ActivitySchedule]] = {}
    for schedule in schedule_rows:
        schedules_by_activity.setdefault(str(schedule.activity_id), []).append(schedule)

    locations_payload = [
        serialize_export_location(location, location_name_by_id)
        for location in locations
    ]
    activities_payload: list[dict[str, Any]] = []

    org_payload = {
        "name": org.name,
        "description": org.description,
        "name_translations": org.name_translations or {},
        "description_translations": org.description_translations or {},
        "manager_id": org.manager_id,
        "phone_country_code": org.phone_country_code,
        "phone_number": org.phone_number,
        "email": org.email,
        "whatsapp": org.whatsapp,
        "facebook": org.facebook,
        "instagram": org.instagram,
        "tiktok": org.tiktok,
        "twitter": org.twitter,
        "xiaohongshu": org.xiaohongshu,
        "wechat": org.wechat,
        "media_urls": org.media_urls or [],
        "logo_media_url": org.logo_media_url,
        "place_id": org.place_id,
        "status": org.status,
        "status_source": org.status_source,
        "source": org.source,
        "source_id": org.source_id,
        "description_source": org.description_source,
        "review_status": org.review_status,
        "review_notes": org.review_notes,
        "locations": locations_payload,
        "activities": activities_payload,
    }

    for activity in activities:
        activity_id = str(activity.id)
        activities_payload.append(
            serialize_export_activity(
                activity,
                pricing_by_activity.get(activity_id, []),
                schedules_by_activity.get(activity_id, []),
                location_name_by_id,
                tzinfo,
                warnings,
            )
        )

    return org_payload


def serialize_export_location(
    location: Location,
    location_name_by_id: dict[str, str],
) -> dict[str, Any]:
    name = location_name_by_id[str(location.id)]
    return {
        "name": name,
        "address": location.address,
        "area_id": str(location.area_id),
        "lat": float(location.lat) if location.lat is not None else None,
        "lng": float(location.lng) if location.lng is not None else None,
    }


def serialize_export_activity(
    activity: Activity,
    pricing_rows: list[ActivityPricing],
    schedule_rows: list[ActivitySchedule],
    location_name_by_id: dict[str, str],
    tzinfo: ZoneInfo,
    warnings: list[str],
) -> dict[str, Any]:
    age_min = getattr(activity.age_range, "lower", None)
    age_max = getattr(activity.age_range, "upper", None)
    activity_payload = {
        "name": activity.name,
        "description": activity.description,
        "name_translations": activity.name_translations or {},
        "description_translations": activity.description_translations or {},
        "category_id": str(activity.category_id),
        "age_min": age_min,
        "age_max": age_max,
        "pricing": [
            serialize_export_pricing(pricing, location_name_by_id, warnings)
            for pricing in pricing_rows
        ],
        "schedules": [
            serialize_export_schedule(
                schedule,
                location_name_by_id,
                tzinfo,
                warnings,
            )
            for schedule in schedule_rows
        ],
    }
    return activity_payload


def serialize_export_pricing(
    pricing: ActivityPricing,
    location_name_by_id: dict[str, str],
    warnings: list[str],
) -> dict[str, Any]:
    location_name = resolve_location_name(
        location_name_by_id,
        pricing.location_id,
        warnings,
    )
    return {
        "location_name": location_name,
        "pricing_type": pricing.pricing_type.value,
        "amount": float(pricing.amount),
        "currency": pricing.currency,
        "sessions_count": pricing.sessions_count,
        "free_trial_class_offered": pricing.free_trial_class_offered,
    }


def serialize_export_schedule(
    schedule: ActivitySchedule,
    location_name_by_id: dict[str, str],
    tzinfo: ZoneInfo,
    warnings: list[str],
) -> dict[str, Any]:
    location_name = resolve_location_name(
        location_name_by_id,
        schedule.location_id,
        warnings,
    )
    entries = [entry_from_utc(entry, tzinfo) for entry in schedule.entries or []]
    return {
        "location_name": location_name,
        "timezone": tzinfo.key,
        "languages": schedule.languages,
        "weekly_entries": entries,
    }


def resolve_location_name(
    location_name_by_id: dict[str, str],
    location_id: str | UUID,
    warnings: list[str],
) -> str:
    key = str(location_id)
    name = location_name_by_id.get(key)
    if name:
        return name
    fallback = f"location-{key}"
    warnings.append(f"Location {key} missing from export map; using {fallback}.")
    return fallback


def entry_from_utc(entry: Any, tzinfo: ZoneInfo) -> dict[str, Any]:
    day_local, start_local, end_local = from_utc_weekly(
        entry.day_of_week_utc,
        entry.start_minutes_utc,
        entry.end_minutes_utc,
        tzinfo,
    )
    return {
        "day_of_week": day_local,
        "start_time": format_minutes(start_local),
        "end_time": format_minutes(end_local),
    }
