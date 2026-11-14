"""Pydantic schemas for activity search responses."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrganizationContactSchema(BaseModel):
    """Public contact details and social links of an organization."""

    model_config = ConfigDict(from_attributes=True)

    website: str | None = None
    email: str | None = None
    phone_country_code: str | None = None
    phone_number: str | None = None
    whatsapp: str | None = None
    facebook: str | None = None
    instagram: str | None = None
    tiktok: str | None = None
    twitter: str | None = None
    xiaohongshu: str | None = None
    wechat: str | None = None


class FeedbackRatingSchema(BaseModel):
    """Count and mean of approved feedback stars for an organization."""

    count: int
    average_stars: Decimal


class FeedbackLabelSchema(BaseModel):
    """A label a parent attached to feedback."""

    id: str
    name: str
    name_translations: dict[str, str] = Field(default_factory=dict)


class FeedbackReviewSchema(BaseModel):
    """One approved feedback entry, without the submitter."""

    id: str
    stars: int
    description: str | None = None
    labels: list[FeedbackLabelSchema] = Field(default_factory=list)
    created_at: datetime


class OrganizationSchema(BaseModel):
    """Organization schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    name_translations: dict[str, str]
    description_translations: dict[str, str]
    media_urls: list[str]
    logo_media_url: str | None
    status: str | None = None
    description_source: str | None = None
    place_id: str | None = None
    parent_verified: bool = False
    parent_verified_at: datetime | None = None
    updated_at: datetime | None = None
    contact: OrganizationContactSchema | None = None
    rating: FeedbackRatingSchema | None = None
    reviews: list[FeedbackReviewSchema] = Field(default_factory=list)


class LocationSchema(BaseModel):
    """Location schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    area_id: str
    region_area_id: str | None
    name: str | None = None
    address: str | None
    lat: Decimal | None
    lng: Decimal | None
    status: str | None = None


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
    kind: str = "class"
    facts: dict[str, bool] = Field(default_factory=dict)
    category_root_id: str | None = None
    category_name: str | None = None
    category_name_translations: dict[str, str] = Field(default_factory=dict)


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
    starts_on: str | None = None
    ends_on: str | None = None


class ActivitySearchResultSchema(BaseModel):
    """Activity search result schema."""

    model_config = ConfigDict(from_attributes=True)

    activity: ActivitySchema
    organization: OrganizationSchema
    location: LocationSchema
    pricing: PricingSchema | None
    schedule: ScheduleSchema | None


class ActivitySearchResponseSchema(BaseModel):
    """Activity search response schema."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ActivitySearchResultSchema]
    next_cursor: str | None = None
    category_match: str = "exact"
    area_scope: list[str] | None = None
    total: int | None = None


_CARD_OMITTED_FIELDS = (
    ("activity", "description"),
    ("activity", "description_translations"),
    ("activity", "facts"),
    ("organization", "description"),
    ("organization", "description_translations"),
    ("organization", "place_id"),
    ("organization", "contact"),
    ("organization", "reviews"),
    ("organization", "updated_at"),
)
# Card rows leave out ``kind`` when it is this; clients read a missing kind
# as a class.
_CARD_DEFAULT_KIND = "class"
# Card rows keep these only when they carry a value.
_CARD_OMITTED_WHEN_EMPTY = (
    ("activity", "category_root_id"),
    ("activity", "category_name"),
    ("activity", "category_name_translations"),
    ("organization", "parent_verified"),
    ("organization", "parent_verified_at"),
    ("organization", "rating"),
    ("location", "name"),
    ("schedule", "starts_on"),
    ("schedule", "ends_on"),
)


def dump_search_response(
    body: ActivitySearchResponseSchema,
    view: str = "full",
    *,
    include_area_scope: bool = True,
) -> dict:
    """Serialize a search response. Card view drops the heavy fields.

    Cursor pages omit ``area_scope``. The first page carries the
    neighbourhood list, and repeating it on every page adds nothing.
    """
    payload = body.model_dump()
    if not include_area_scope:
        payload.pop("area_scope", None)
    if payload.get("total") is None:
        payload.pop("total", None)
    if view != "card":
        return payload
    for item in payload.get("items", []):
        _apply_card_view(item)
    return payload


def _drop_duplicate_english_name(section: dict, name_key: str = "name") -> None:
    translations_key = f"{name_key}_translations"
    translations = section.get(translations_key)
    if not isinstance(translations, dict):
        return
    if translations.get("en") == section.get(name_key):
        trimmed = dict(translations)
        trimmed.pop("en", None)
        section[translations_key] = trimmed


def _apply_card_view(item: dict) -> None:
    for section, field in _CARD_OMITTED_FIELDS:
        section_payload = item.get(section)
        if isinstance(section_payload, dict):
            section_payload.pop(field, None)
    activity = item.get("activity")
    if isinstance(activity, dict):
        _drop_duplicate_english_name(activity, "category_name")
        if activity.get("kind") == _CARD_DEFAULT_KIND:
            activity.pop("kind")
    for section, field in _CARD_OMITTED_WHEN_EMPTY:
        section_payload = item.get(section)
        if isinstance(section_payload, dict) and not section_payload.get(field):
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
