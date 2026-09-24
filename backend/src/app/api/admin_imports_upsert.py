"""Upsert helpers for admin imports."""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import (
    CATALOG_MANAGER_REQUIRED,
    NO_MATCH_TO_CLOSE,
    coerce_uuid,
    find_import_organization,
    parse_org_status,
    parse_place_id,
    stamp_imported_organization,
)
from app.api.admin_imports_fields import (
    guard_import_organization_update,
    manager_ids_match,
)
from app.api.admin_imports_lookups import (
    filter_fields,
    guard_existing_org,
    merge_schedule_entries,
    parse_weekly_entries_local,
    prepare_listing_body,
    resolve_activity_category_fields,
    resolve_location_area_fields,
)
from app.api.admin_imports_venues import (
    LINKED_VENUE_WARNING,
    link_activity_to_venue,
)
from app.api.admin_imports_utils import (
    parse_timezone,
    persist_import_change,
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
from app.db.models import Activity
from app.db.models import ActivityPricing, ActivitySchedule
from app.db.models import Location, Organization, PricingType
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
    "name_zh",
    "description_zh",
    "place_id",
    "status",
    "source",
    "source_id",
    "description_source",
}
ALLOWED_LOCATION_FIELDS = {
    "name",
    "address",
    "area_id",
    "area_name",
    "lat",
    "lng",
    "place_id",
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
    "name_zh",
    "description_zh",
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


def upsert_organization(
    session: Session,
    raw_org: dict[str, Any],
    *,
    dry_run: bool = False,
    allow_updates: bool = False,
    catalog_manager_id: str | None = None,
    warnings: list[str] | None = None,
    import_job_id: Any = None,
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
        existing = find_import_organization(session, raw_org)
        if existing is None:
            existing = repo.find_by_name_case_insensitive(name)
    except MultipleResultsFound as exc:
        raise ValidationError(
            "Multiple organizations found",
            field="name",
        ) from exc

    body = filter_fields(raw_org, ALLOWED_ORG_FIELDS)
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
        "name_zh",
        "description_zh",
    ):
        body.pop(extra, None)
    prepare_listing_body(body)
    requested_status = parse_org_status(raw_org.get("status"))

    if existing:
        guard_existing_org(
            existing,
            body,
            allow_updates=allow_updates,
            catalog_manager_id=catalog_manager_id,
        )
        if not allow_updates:
            return existing, "skipped"
        guard_import_organization_update(existing, body)
        if requested_status:
            if existing.status_source == "owner":
                if warnings is not None:
                    warnings.append(
                        "owner listing status preserved; importer status ignored"
                    )
            else:
                body["status"] = requested_status
                body["status_source"] = "importer"
        updated = _update_organization(repo, existing, body)
        stamp_imported_organization(
            updated,
            created=False,
            import_job_id=import_job_id,
        )
        repo.update(updated)
        persist_import_change(session, dry_run=dry_run)
        session.refresh(updated)
        return updated, "updated"

    if requested_status == "closed_permanently":
        raise ValidationError(NO_MATCH_TO_CLOSE, field="status")
    if catalog_manager_id and not manager_ids_match(
        body.get("manager_id"),
        catalog_manager_id,
    ):
        raise ValidationError(CATALOG_MANAGER_REQUIRED, field="manager_id")
    if not raw_org.get("manager_id"):
        raise ValidationError("manager_id is required", field="manager_id")
    if requested_status:
        body["status"] = requested_status
        body["status_source"] = "importer"
    created = _create_organization(repo, body)
    stamp_imported_organization(
        created,
        created=True,
        import_job_id=import_job_id,
    )
    repo.create(created)
    persist_import_change(session, dry_run=dry_run)
    session.refresh(created)
    return created, "created"


def _find_import_location(
    repo: LocationRepository,
    org: Organization,
    raw_location: dict[str, Any],
    address_value: str,
    warnings: list[str] | None = None,
) -> Location | None:
    """Match a location by place_id, then org + address."""
    place_id = parse_place_id(raw_location.get("place_id"))
    if place_id:
        found = repo.find_by_place_id(place_id)
        if found is not None:
            if str(found.org_id) == str(org.id):
                return found
            if warnings is not None:
                warnings.append(
                    "place_id already used by another organization; matching by address"
                )
            raw_location.pop("place_id", None)
    return repo.find_by_org_and_address_case_insensitive(
        coerce_uuid(org.id),
        address_value,
    )


def upsert_location(
    session: Session,
    org: Organization,
    raw_location: dict[str, Any],
    address_value: str,
    *,
    dry_run: bool = False,
    allow_updates: bool = True,
    warnings: list[str] | None = None,
) -> tuple[Location, str]:
    repo = LocationRepository(session)
    try:
        existing = _find_import_location(
            repo,
            org,
            raw_location,
            address_value,
            warnings,
        )
    except MultipleResultsFound as exc:
        raise ValidationError("Multiple locations found", field="name") from exc

    if existing and not allow_updates:
        return existing, "skipped"

    body = filter_fields(raw_location, ALLOWED_LOCATION_FIELDS)
    resolve_location_area_fields(session, body)
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
        existing = repo.find_by_org_and_name_case_insensitive(coerce_uuid(org.id), name)
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

    body = filter_fields(raw_activity, ALLOWED_ACTIVITY_FIELDS)
    resolve_activity_category_fields(session, body)
    body.pop("pricing", None)
    body.pop("schedules", None)
    body.pop("source_url", None)
    body.pop("vetting_note", None)
    body.pop("name_zh", None)
    body.pop("description_zh", None)
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
            coerce_uuid(activity.id),
            coerce_uuid(location.id),
            pricing_enum,
        )
    except MultipleResultsFound as exc:
        raise ValidationError(
            "Multiple pricing entries found",
            field="pricing_type",
        ) from exc

    if existing and not allow_updates:
        return existing, "skipped"

    body = filter_fields(raw_pricing, ALLOWED_PRICING_FIELDS)
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
        coerce_uuid(activity.id),
        coerce_uuid(location.id),
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
