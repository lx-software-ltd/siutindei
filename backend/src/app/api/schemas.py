"""Pydantic schemas for activity search responses."""

from __future__ import annotations

from decimal import Decimal
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class OrganizationSchema(BaseModel):
    """Organization schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    name_translations: dict[str, str]
    description_translations: dict[str, str]
    manager_id: str
    media_urls: List[str]
    logo_media_url: Optional[str]
    status: Optional[str] = None
    description_source: Optional[str] = None
    place_id: Optional[str] = None


class LocationSchema(BaseModel):
    """Location schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    area_id: str
    region_area_id: Optional[str]
    address: Optional[str]
    lat: Optional[Decimal]
    lng: Optional[Decimal]


class ActivitySchema(BaseModel):
    """Activity schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    name_translations: dict[str, str]
    description_translations: dict[str, str]
    age_min: Optional[int]
    age_max: Optional[int]
    category_id: Optional[str]


class PricingSchema(BaseModel):
    """Pricing schema."""

    model_config = ConfigDict(from_attributes=True)

    pricing_type: str
    amount: Decimal
    currency: str
    sessions_count: Optional[int]
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
    weekly_entries: List[ScheduleEntrySchema]
    languages: List[str]


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

    items: List[ActivitySearchResultSchema]
    next_cursor: Optional[str] = None
