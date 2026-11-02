"""Pydantic schemas for activity search responses."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OrganizationSchema(BaseModel):
    """Organization schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    name_translations: dict[str, str]
    description_translations: dict[str, str]
    manager_id: str
    media_urls: list[str]
    logo_media_url: str | None
    status: str | None = None
    description_source: str | None = None
    place_id: str | None = None


class LocationSchema(BaseModel):
    """Location schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    area_id: str
    region_area_id: str | None
    address: str | None
    lat: Decimal | None
    lng: Decimal | None


class ActivitySchema(BaseModel):
    """Activity schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    name_translations: dict[str, str]
    description_translations: dict[str, str]
    age_min: int | None
    age_max: int | None
    category_id: str | None


class PricingSchema(BaseModel):
    """Pricing schema."""

    model_config = ConfigDict(from_attributes=True)

    pricing_type: str
    amount: Decimal
    currency: str
    sessions_count: int | None
    free_trial_class_offered: bool


class ScheduleEntrySchema(BaseModel):
    """Schedule entry schema."""

    model_config = ConfigDict(from_attributes=True)

    day_of_week_utc: int
    start_minutes_utc: int
    end_minutes_utc: int


class ScheduleSchema(BaseModel):
    """Schedule schema."""

    model_config = ConfigDict(from_attributes=True)

    schedule_type: str
    weekly_entries: list[ScheduleEntrySchema]
    languages: list[str]


class ActivitySearchResultSchema(BaseModel):
    """Activity search result schema."""

    model_config = ConfigDict(from_attributes=True)

    activity: ActivitySchema
    organization: OrganizationSchema
    location: LocationSchema
    pricing: PricingSchema
    schedule: ScheduleSchema


class ActivitySearchResponseSchema(BaseModel):
    """Activity search response schema."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ActivitySearchResultSchema]
    next_cursor: str | None = None
    category_match: str = "exact"


_CARD_OMITTED_FIELDS = (
    ("activity", "description"),
    ("activity", "description_translations"),
    ("organization", "description"),
    ("organization", "description_translations"),
    ("organization", "manager_id"),
    ("organization", "place_id"),
)


def dump_search_response(
    body: ActivitySearchResponseSchema,
    view: str = "full",
) -> dict:
    """Serialize a search response. Card view drops the heavy fields."""
    payload = body.model_dump()
    if view != "card":
        return payload
    for item in payload.get("items", []):
        _apply_card_view(item)
    return payload


def _drop_duplicate_english_name(section: dict) -> None:
    translations = section.get("name_translations")
    if not isinstance(translations, dict):
        return
    if translations.get("en") == section.get("name"):
        trimmed = dict(translations)
        trimmed.pop("en", None)
        section["name_translations"] = trimmed


def _apply_card_view(item: dict) -> None:
    for section, field in _CARD_OMITTED_FIELDS:
        section_payload = item.get(section)
        if isinstance(section_payload, dict):
            section_payload.pop(field, None)
    for section_name in ("activity", "organization"):
        section_payload = item.get(section_name)
        if isinstance(section_payload, dict):
            _drop_duplicate_english_name(section_payload)
    organization = item.get("organization")
    if isinstance(organization, dict):
        media_urls = organization.get("media_urls") or []
        organization["media_urls"] = list(media_urls)[:1]
    schedule = item.get("schedule")
    if isinstance(schedule, dict):
        entries = schedule.get("weekly_entries") or []
        schedule["weekly_entries"] = list(entries)[:1]
