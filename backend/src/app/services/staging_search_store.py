"""In-memory activity search backed by a staging JSON fixture."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from app.api.schemas import (
    ActivitySchema,
    ActivitySearchResponseSchema,
    ActivitySearchResultSchema,
    FeedbackRatingSchema,
    FeedbackReviewSchema,
    LocationSchema,
    OrganizationContactSchema,
    OrganizationSchema,
    PricingSchema,
    ScheduleEntrySchema,
    ScheduleSchema,
)
from app.db.queries import (
    UNPRICED_SORT_KEY,
    ActivitySearchFilters,
    applied_search_area_scope,
    class_price_value,
    hong_kong_day,
    search_area_scope_labels,
    validate_filters,
)

_FIXTURE_CACHE: dict[str, Any] | None = None
_SORTED_PUBLISHED_ITEMS: list[dict[str, Any]] | None = None
_LFS_POINTER_PREFIX = "version https://git-lfs.github.com/spec/v1"


def staging_search_data_enabled() -> bool:
    """Return True when staging fixture search is enabled."""

    raw = os.environ.get("STAGING_SEARCH_DATA_ENABLED", "").strip().lower()
    return raw in {"1", "true", "yes"}


def fetch_staging_search_response(
    filters: ActivitySearchFilters,
) -> ActivitySearchResponseSchema:
    """Search activities from the staging JSON fixture."""

    validate_filters(filters)
    payload = _load_fixture()
    meta = payload.get("meta", {})
    area_descendants: dict[str, list[str]] = meta.get("area_descendants", {})
    category_descendants = meta.get("category_descendants")

    matched = [
        item
        for item in _sorted_published_items()
        if _matches(item, filters, area_descendants, category_descendants)
    ]
    if filters.sort == "price":
        matched.sort(key=_price_sort_key)
    row_key = _price_sort_key if filters.sort == "price" else _sort_key

    requested_limit = filters.limit
    start_index = 0
    if filters.cursor is not None:
        time_key = (
            filters.cursor.day_of_week_utc,
            filters.cursor.start_minutes_utc,
            str(filters.cursor.schedule_id),
        )
        cursor_key: tuple[Any, ...] = time_key
        if filters.sort == "price":
            price_key = filters.cursor.price_key
            cursor_key = (
                price_key if price_key is not None else UNPRICED_SORT_KEY,
                *time_key,
            )
        for index, row in enumerate(matched):
            if row_key(row) > cursor_key:
                start_index = index
                break
        else:
            start_index = len(matched)

    page = matched[start_index : start_index + requested_limit + 1]
    has_more = len(page) > requested_limit
    trimmed = page[:requested_limit]

    next_cursor = None
    if has_more and trimmed:
        last = trimmed[-1]
        sort_meta = last["_sort"]
        next_cursor = _encode_cursor(
            sort_meta["day_of_week_utc"],
            sort_meta["start_minutes_utc"],
            UUID(sort_meta["schedule_id"]),
            sort=filters.sort,
            price_key=_price_sort_key(last)[0] if filters.sort == "price" else None,
        )

    total = None
    if filters.include_total and filters.cursor is None:
        total = len({row["activity"]["id"] for row in matched})
    detail = filters.activity_id is not None
    return ActivitySearchResponseSchema(
        items=[_to_schema(row, filters.view, detail=detail) for row in trimmed],
        next_cursor=next_cursor,
        area_scope=search_area_scope_labels(),
        total=total,
    )


def _class_price(row: dict[str, Any]) -> Decimal | None:
    pricing = row.get("pricing") or {}
    raw_amount = pricing.get("amount")
    return class_price_value(
        pricing.get("pricing_type"),
        None if raw_amount is None else Decimal(str(raw_amount)),
        pricing.get("sessions_count"),
    )


def _price_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    price = _class_price(row)
    return (price if price is not None else UNPRICED_SORT_KEY, *_sort_key(row))


def _load_fixture() -> dict[str, Any]:
    global _FIXTURE_CACHE, _SORTED_PUBLISHED_ITEMS
    if _FIXTURE_CACHE is not None:
        return _FIXTURE_CACHE

    path = _resolve_fixture_path()
    _FIXTURE_CACHE = _read_fixture_json(path)
    _SORTED_PUBLISHED_ITEMS = None
    return _FIXTURE_CACHE


def _read_fixture_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if raw.startswith(_LFS_POINTER_PREFIX):
        raise FileNotFoundError(
            "Staging search fixture is a Git LFS pointer; run git lfs pull "
            "or set STAGING_SEARCH_DATA_PATH to a materialized JSON file."
        )
    return json.loads(raw)


def _sorted_published_items() -> list[dict[str, Any]]:
    """Return fixture rows sorted for search, excluding hidden listings."""

    global _SORTED_PUBLISHED_ITEMS
    if _SORTED_PUBLISHED_ITEMS is not None:
        return _SORTED_PUBLISHED_ITEMS

    items = [
        _normalize_item(item)
        for item in _load_fixture().get("items", [])
        if _is_visible_listing(item)
    ]
    items.sort(key=_sort_key)
    _SORTED_PUBLISHED_ITEMS = items
    return _SORTED_PUBLISHED_ITEMS


def _is_visible_listing(item: dict[str, Any]) -> bool:
    status = item.get("organization", {}).get("status")
    if status in {"closed_permanently", "hidden"}:
        return False
    location_status = item.get("location", {}).get("status")
    return location_status != "permanently_closed"


def _resolve_fixture_path() -> Path:
    env_path = os.environ.get("STAGING_SEARCH_DATA_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path
        raise FileNotFoundError(f"Staging fixture not found: {path}")

    candidates = [
        Path("/var/task/fixtures/activity_search_staging.json"),
        Path(__file__).resolve().parents[3] / "fixtures/activity_search_staging.json",
        Path(__file__).resolve().parents[4]
        / "shared"
        / "fixtures"
        / "activity_search_staging.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Staging search fixture not found. Set STAGING_SEARCH_DATA_PATH."
    )


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    sort_meta = item.get("_sort")
    if sort_meta is not None:
        return item

    schedule = item.get("schedule", {})
    entries = schedule.get("weekly_entries") or []
    if not entries:
        raise ValueError("Fixture item missing weekly_entries for sort key")
    first = sorted(
        entries,
        key=lambda entry: (
            entry["day_of_week_utc"],
            entry["start_minutes_utc"],
            entry["end_minutes_utc"],
        ),
    )[0]
    schedule_id = _uuid_from_parts(
        item["activity"]["id"],
        item["location"]["id"],
        ",".join(schedule.get("languages") or []),
    )
    normalized = dict(item)
    normalized["_sort"] = {
        "day_of_week_utc": first["day_of_week_utc"],
        "start_minutes_utc": first["start_minutes_utc"],
        "schedule_id": schedule_id,
    }
    return normalized


@lru_cache(maxsize=1)
def _uuid_from_parts(activity_id: str, location_id: str, languages: str) -> str:
    from uuid import uuid5

    namespace = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    return str(uuid5(namespace, f"{activity_id}:{location_id}:{languages}"))


def _sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    sort_meta = row["_sort"]
    return (
        sort_meta["day_of_week_utc"],
        sort_meta["start_minutes_utc"],
        sort_meta["schedule_id"],
    )


def _matches(
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
        class_price = _class_price(item)
        if class_price is None or class_price > filters.class_price_max:
            return False

    scope = applied_search_area_scope(filters)
    if scope is not None and str(location.get("area_id") or "") not in {
        str(area_id) for area_id in scope
    }:
        return False

    if filters.age is not None:
        age_min = activity.get("age_min")
        age_max = activity.get("age_max")
        if age_min is None or age_max is None:
            return False
        if not (age_min <= filters.age <= age_max):
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

    entries = schedule.get("weekly_entries") or []
    if not _entries_match(entries, filters):
        return False

    return not (filters.text_query and not _text_matches(item, filters.text_query))


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


def _to_schema(
    row: dict[str, Any],
    view: str = "full",
    *,
    detail: bool = False,
) -> ActivitySearchResultSchema:
    activity = row["activity"]
    organization = row["organization"]
    location = row["location"]
    pricing = row["pricing"]
    schedule = row["schedule"]
    card = view == "card"
    media_urls = list(organization.get("media_urls") or [])
    entries = list(schedule.get("weekly_entries") or [])
    if card:
        media_urls = media_urls[:1]
        entries = _sorted_entries(entries)[:1]

    return ActivitySearchResultSchema(
        activity=ActivitySchema(
            id=activity["id"],
            name=activity["name"],
            description=None if card else activity.get("description"),
            name_translations=activity.get("name_translations") or {},
            description_translations=(
                {} if card else activity.get("description_translations") or {}
            ),
            age_min=activity.get("age_min"),
            age_max=activity.get("age_max"),
            category_id=activity.get("category_id"),
        ),
        organization=OrganizationSchema(
            id=organization["id"],
            name=organization["name"],
            description=None if card else organization.get("description"),
            name_translations=organization.get("name_translations") or {},
            description_translations=(
                {} if card else organization.get("description_translations") or {}
            ),
            media_urls=media_urls,
            logo_media_url=organization.get("logo_media_url"),
            status=organization.get("status"),
            description_source=organization.get("description_source"),
            place_id=organization.get("place_id") if detail else None,
            parent_verified=bool(organization.get("parent_verified", False)),
            updated_at=organization.get("updated_at"),
            contact=(
                None
                if card or not organization.get("contact")
                else OrganizationContactSchema(**organization["contact"])
            ),
            rating=(
                FeedbackRatingSchema(**organization["rating"])
                if organization.get("rating")
                else None
            ),
            reviews=(
                [
                    FeedbackReviewSchema(**review)
                    for review in organization.get("reviews") or []
                ]
                if detail and not card
                else []
            ),
        ),
        location=LocationSchema(
            id=location["id"],
            area_id=location["area_id"],
            region_area_id=location.get("region_area_id"),
            name=location.get("name"),
            address=location.get("address"),
            lat=location.get("lat"),
            lng=location.get("lng"),
            status=location.get("status") or "open",
        ),
        pricing=PricingSchema(
            pricing_type=pricing["pricing_type"],
            amount=Decimal(str(pricing["amount"])),
            currency=pricing.get("currency", "HKD"),
            sessions_count=pricing.get("sessions_count"),
            free_trial_class_offered=bool(
                pricing.get("free_trial_class_offered", False)
            ),
        ),
        schedule=ScheduleSchema(
            schedule_type=schedule.get("schedule_type", "weekly"),
            weekly_entries=[
                ScheduleEntrySchema(
                    day_of_week_utc=entry["day_of_week_utc"],
                    start_minutes_utc=entry["start_minutes_utc"],
                    end_minutes_utc=entry["end_minutes_utc"],
                )
                for entry in entries
            ],
            languages=schedule.get("languages") or [],
        ),
    )


def _sorted_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda entry: (
            entry.get("day_of_week_utc", 0),
            entry.get("start_minutes_utc", 0),
            entry.get("end_minutes_utc", 0),
        ),
    )


def _encode_cursor(
    day_of_week_utc: int,
    start_minutes_utc: int,
    schedule_id: UUID,
    *,
    sort: str = "time",
    price_key: Decimal | None = None,
) -> str:
    import base64

    body: dict[str, Any] = {
        "schedule_id": str(schedule_id),
        "day_of_week_utc": day_of_week_utc,
        "start_minutes_utc": start_minutes_utc,
    }
    if sort != "time":
        body["sort"] = sort
        body["price_key"] = None if price_key is None else str(price_key)
    payload = json.dumps(body).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("utf-8")
    return encoded.rstrip("=")
