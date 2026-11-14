"""Filter matching for the in-memory staging search fixture."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from app.db.queries import (
    ActivitySearchFilters,
    applied_search_area_scope,
    search_today,
)
from app.db.search_conditions import class_price_value, hong_kong_day
from app.services.schedule_dates import parse_schedule_date, schedule_dates_match


def row_class_price(row: dict[str, Any]) -> Decimal | None:
    pricing = row.get("pricing") or {}
    raw_amount = pricing.get("amount")
    return class_price_value(
        pricing.get("pricing_type"),
        None if raw_amount is None else Decimal(str(raw_amount)),
        pricing.get("sessions_count"),
    )


def matches(
    item: dict[str, Any],
    filters: ActivitySearchFilters,
    area_descendants: dict[str, list[str]],
    category_descendants: dict[str, list[str]] | None,
) -> bool:
    activity = item["activity"]
    location = item["location"]
    pricing = item["pricing"]
    schedule = item["schedule"]

    if filters.activity_id is not None and UUID(activity["id"]) != filters.activity_id:
        return False

    if filters.org_ids and UUID(item["organization"]["id"]) not in set(filters.org_ids):
        return False

    if filters.free_trial and not pricing.get("free_trial_class_offered"):
        return False

    if filters.class_price_max is not None:
        class_price = row_class_price(item)
        if class_price is None or class_price > filters.class_price_max:
            return False

    scope = applied_search_area_scope(filters)
    if scope is not None and str(location.get("area_id") or "") not in {
        str(area_id) for area_id in scope
    }:
        return False

    if not _listing_matches(item, filters):
        return False

    if filters.area_id is not None:
        allowed = area_descendants.get(str(filters.area_id), [str(filters.area_id)])
        if location.get("area_id") not in allowed:
            return False

    if filters.category_ids:
        if category_descendants:
            category_ids_allowed: set[str] = set()
            for value in filters.category_ids:
                key = str(value)
                category_ids_allowed.update(category_descendants.get(key, [key]))
            if activity.get("category_id") not in category_ids_allowed:
                return False
        elif activity.get("category_id") not in {
            str(value) for value in filters.category_ids
        }:
            return False

    if (
        filters.pricing_type is not None
        and pricing.get("pricing_type") != filters.pricing_type.value
    ):
        return False

    if (
        filters.price_min is not None
        and Decimal(str(pricing.get("amount", 0))) < filters.price_min
    ):
        return False

    if (
        filters.price_max is not None
        and Decimal(str(pricing.get("amount", 0))) > filters.price_max
    ):
        return False

    if (
        filters.schedule_type is not None
        and schedule.get("schedule_type") != filters.schedule_type.value
    ):
        return False

    if filters.languages:
        langs = schedule.get("languages") or []
        if not any(language in langs for language in filters.languages):
            return False

    if not _dates_match(schedule, filters):
        return False

    entries = schedule.get("weekly_entries") or []
    if not _entries_match(entries, filters):
        return False

    return not (filters.text_query and not _text_matches(item, filters.text_query))


def _dates_match(schedule: dict[str, Any], filters: ActivitySearchFilters) -> bool:
    return schedule_dates_match(
        parse_schedule_date(schedule.get("starts_on"), "starts_on"),
        parse_schedule_date(schedule.get("ends_on"), "ends_on"),
        search_today(filters),
        filters.date_from,
        filters.date_to,
    )


def _listing_matches(item: dict[str, Any], filters: ActivitySearchFilters) -> bool:
    """Python twin of ``listing_conditions``. A row without ``kind`` is a class."""
    activity = item["activity"]
    if filters.kinds and (activity.get("kind") or "class") not in filters.kinds:
        return False
    verified = bool((item.get("organization") or {}).get("parent_verified"))
    if not verified and (filters.verified_only or activity.get("kind") == "eat"):
        return False
    wants_range = filters.age_min is not None or filters.age_max is not None
    if filters.age is None and not wants_range:
        return True
    age_min = activity.get("age_min")
    age_max = activity.get("age_max")
    if age_min is None or age_max is None:
        return False
    if filters.age is not None and not age_min <= filters.age <= age_max:
        return False
    if filters.age_min is not None and age_max < filters.age_min:
        return False
    return not (filters.age_max is not None and age_min > filters.age_max)


def _text_matches(item: dict[str, Any], text_query: str) -> bool:
    """Case-insensitive match on names and name translation values."""
    needle = text_query.casefold()
    activity = item.get("activity") or {}
    organization = item.get("organization") or {}
    values = [activity.get("name") or "", organization.get("name") or ""]
    for translations in (
        activity.get("name_translations") or {},
        organization.get("name_translations") or {},
    ):
        if isinstance(translations, dict):
            values.extend(translations.values())
    return any(needle in str(value).casefold() for value in values)


def _entries_match(
    entries: list[dict[str, Any]],
    filters: ActivitySearchFilters,
) -> bool:
    if (
        filters.day_of_week_utc is None
        and filters.start_minutes_utc is None
        and filters.end_minutes_utc is None
        and not filters.days_of_week_hkt
    ):
        return True

    for entry in entries:
        if (
            filters.day_of_week_utc is not None
            and entry.get("day_of_week_utc") != filters.day_of_week_utc
        ):
            continue

        if filters.days_of_week_hkt and (
            hong_kong_day(
                int(entry.get("day_of_week_utc", 0)),
                int(entry.get("start_minutes_utc", 0)),
            )
            not in filters.days_of_week_hkt
        ):
            continue

        start = entry.get("start_minutes_utc")
        end = entry.get("end_minutes_utc")
        if start is None or end is None:
            continue

        if (
            filters.start_minutes_utc is not None
            and filters.end_minutes_utc is not None
        ):
            if start < end:
                if start < filters.end_minutes_utc and end > filters.start_minutes_utc:
                    return True
            elif filters.end_minutes_utc > start or filters.start_minutes_utc < end:
                return True
            continue

        if filters.start_minutes_utc is not None:
            if start > end or end >= filters.start_minutes_utc:
                return True
            continue

        if filters.end_minutes_utc is not None:
            if start > end or start <= filters.end_minutes_utc:
                return True
            continue

        return True

    return False
