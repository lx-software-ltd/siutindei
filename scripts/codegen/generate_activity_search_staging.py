#!/usr/bin/env python3
"""Generate staging activity search fixture (at least 3000 HK rows)."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from app.data.hk_neighbourhoods import NEIGHBOURHOODS, neighbourhoods_for

OUTPUT = ROOT / "shared" / "fixtures" / "activity_search_staging.json"

NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

HK_ISLAND_REGION = "a1111111-1111-1111-1111-111111111101"
KOWLOON_REGION = "a1111111-1111-1111-1111-111111111102"
NEW_TERRITORIES_REGION = "a1111111-1111-1111-1111-111111111103"
ISLANDS_REGION = "a1111111-1111-1111-1111-111111111104"

AGE_GROUPS: list[tuple[str, int, int, int]] = [
    ("1-3", 2, 1, 3),
    ("3-6", 4, 3, 6),
    ("6-12", 9, 6, 12),
]

PRICING_TYPES: list[tuple[str, str, float, int | None]] = [
    ("per_class", "per class", 150.0, None),
    ("per_sessions", "per term", 1200.0, 8),
    ("per_hour", "per hour", 80.0, None),
    ("per_day", "per day", 400.0, None),
    ("free", "free", 0.0, None),
]

CATEGORY_PREFIX = "c1111111-1111-1111-1111-11111111"


class StagingCategory(NamedTuple):
    """Where staging rows sit, and the kind each schedule variant gets."""

    category_id: str
    root_id: str
    label: str
    label_zh: str
    kinds: tuple[str, ...]
    pricing_types: tuple[str, ...]
    age_keys: tuple[str, ...] = tuple(row[0] for row in AGE_GROUPS)


_ALL_PRICES = tuple(row[0] for row in PRICING_TYPES)


def _topic(suffix: str, label: str, label_zh: str) -> StagingCategory:
    category_id = CATEGORY_PREFIX + suffix
    return StagingCategory(
        category_id, category_id, label, label_zh, ("class", "camp"), _ALL_PRICES
    )


# The nine wizard topics from 0066. Variant 0 is a class, variant 1 a camp.
TOPICS: list[StagingCategory] = [
    _topic("1301", "Baby and toddler", "嬰幼兒及親子"),
    _topic("1302", "Sports", "運動"),
    _topic("1303", "Swimming and water sports", "游泳及水上活動"),
    _topic("1304", "Art and making", "藝術及手作"),
    _topic("1305", "Music, dance and drama", "音樂、舞蹈及戲劇"),
    _topic("1306", "Languages", "語言"),
    _topic("1307", "STEM and coding", "STEM 及編程"),
    _topic("1308", "Tutoring and exam preparation", "補習及應試"),
    _topic("1309", "Outdoors, scouts and community", "戶外、童軍及社區"),
]

# One leaf under each listed fixed root. The root decides the kind.
FIXED_LEAVES: list[StagingCategory] = [
    StagingCategory(
        CATEGORY_PREFIX + "1411",
        CATEGORY_PREFIX + "1401",
        "Playground and park",
        "遊樂場及公園",
        ("place", "place"),
        ("free",),
    ),
    StagingCategory(
        CATEGORY_PREFIX + "1422",
        CATEGORY_PREFIX + "1402",
        "Kindergarten",
        "幼稚園",
        ("preschool", "preschool"),
        ("per_sessions",),
        ("1-3", "3-6"),
    ),
]

CATEGORIES: list[StagingCategory] = [*TOPICS, *FIXED_LEAVES]

KIND_WORDS = {
    "class": "class",
    "camp": "camp",
    "place": "",
    "preschool": "",
}

FACTS_BY_KIND: dict[str, dict[str, bool]] = {
    "class": {},
    "camp": {"lunch_included": True},
    "place": {"toilets": True, "shade": False, "stroller_access": True},
    "preschool": {},
}

# Every third district's organisers are parent-verified. The date is fixed
# so items do not change between runs.
VERIFIED_EVERY = 3
VERIFIED_AT = "2026-11-01T02:00:00+00:00"
CAMP_SESSION_DAYS = 7

DISTRICTS: list[tuple[str, str]] = [
    ("Central and Western", HK_ISLAND_REGION),
    ("Eastern", HK_ISLAND_REGION),
    ("Southern", HK_ISLAND_REGION),
    ("Wan Chai", HK_ISLAND_REGION),
    ("Kowloon City", KOWLOON_REGION),
    ("Kwun Tong", KOWLOON_REGION),
    ("Sham Shui Po", KOWLOON_REGION),
    ("Wong Tai Sin", KOWLOON_REGION),
    ("Yau Tsim Mong", KOWLOON_REGION),
    ("Islands", ISLANDS_REGION),
    ("Kwai Tsing", NEW_TERRITORIES_REGION),
    ("North", NEW_TERRITORIES_REGION),
    ("Sai Kung", NEW_TERRITORIES_REGION),
    ("Sha Tin", NEW_TERRITORIES_REGION),
    ("Tai Po", NEW_TERRITORIES_REGION),
    ("Tsuen Wan", NEW_TERRITORIES_REGION),
    ("Tuen Mun", NEW_TERRITORIES_REGION),
    ("Yuen Long", NEW_TERRITORIES_REGION),
]

# Two weekly slots keep every category, age, district, and price in the
# fixture without doubling the file the staging site downloads.
SCHEDULE_VARIANTS: list[tuple[int, int, int]] = [
    (1, 600, 660),
    (6, 540, 600),
]

REGION_LABELS = {
    HK_ISLAND_REGION: "Hong Kong Island",
    KOWLOON_REGION: "Kowloon",
    NEW_TERRITORIES_REGION: "New Territories",
    ISLANDS_REGION: "Islands",
}


def _uuid(key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, key))


def _district_id(name: str) -> str:
    return _uuid(f"siutindei.hk.district.{name}")


def _build_area_descendants() -> dict[str, list[str]]:
    by_region: dict[str, list[str]] = {
        HK_ISLAND_REGION: [],
        KOWLOON_REGION: [],
        NEW_TERRITORIES_REGION: [],
        ISLANDS_REGION: [],
    }
    descendants: dict[str, list[str]] = {}
    for name, region_id in DISTRICTS:
        district_id = _district_id(name)
        hood_ids = [str(item.id) for item in neighbourhoods_for(name)]
        by_region[region_id].append(district_id)
        by_region[region_id].extend(hood_ids)
        descendants[district_id] = [district_id, *hood_ids]
        for hood_id in hood_ids:
            descendants[hood_id] = [hood_id]
    for region_id, area_ids in by_region.items():
        descendants[region_id] = list(area_ids)
    return descendants


def _build_category_descendants() -> dict[str, list[str]]:
    """Each topic and leaf matches itself; a fixed root also matches its leaf."""
    descendants: dict[str, list[str]] = {}
    for category in CATEGORIES:
        descendants.setdefault(category.root_id, [category.root_id])
        if category.category_id != category.root_id:
            descendants[category.root_id].append(category.category_id)
            descendants[category.category_id] = [category.category_id]
    return descendants


def _listing_label(category: StagingCategory, kind: str) -> str:
    word = KIND_WORDS[kind]
    return f"{category.label} {word}" if word else category.label


def _camp_session() -> tuple[str, str]:
    """A week next July, so every weekday occurs and the session has not ended."""
    starts_on = date(datetime.now(tz=UTC).year + 1, 7, 6)
    ends_on = starts_on + timedelta(days=CAMP_SESSION_DAYS - 1)
    return starts_on.isoformat(), ends_on.isoformat()


def _schedule(kind: str, day: int, start: int, end: int) -> dict[str, Any]:
    schedule: dict[str, Any] = {
        "schedule_type": "weekly",
        "weekly_entries": [
            {
                "day_of_week_utc": day,
                "start_minutes_utc": start,
                "end_minutes_utc": end,
            }
        ],
        "languages": ["en"],
    }
    if kind == "camp":
        schedule["starts_on"], schedule["ends_on"] = _camp_session()
    return schedule


def _build_item(
    *,
    category: StagingCategory,
    kind: str,
    age_key: str,
    age_min: int,
    age_max: int,
    district_name: str,
    region_id: str,
    verified: bool,
    pricing_type: str,
    pricing_label: str,
    amount: float,
    sessions_count: int | None,
    variant: int,
    day: int,
    start: int,
    end: int,
    hood_index: int,
) -> dict[str, Any]:
    hoods = neighbourhoods_for(district_name)
    hood = hoods[hood_index % len(hoods)]
    cat_id = category.category_id
    cat_label = category.label
    cell_key = f"{cat_id}:{age_key}:{district_name}:{pricing_type}:{variant}"
    activity_id = _uuid(f"siutindei.staging.activity.{cell_key}")
    org_id = _uuid(f"siutindei.staging.org.{cat_id}:{district_name}")
    location_id = _uuid(f"siutindei.staging.location.{district_name}.{hood.name}")
    schedule_id = _uuid(f"siutindei.staging.schedule.{cell_key}")

    listing_label = _listing_label(category, kind)
    title = (
        f"{listing_label} in {district_name} "
        f"(ages {age_min}–{age_max}, {pricing_label})"
    )
    description = (
        f"Staging listing for {listing_label.lower()} in {district_name}, "
        f"Hong Kong. Suitable for ages {age_min} to {age_max}. "
        f"Sessions run in English."
    )
    region_label = REGION_LABELS.get(region_id, "Hong Kong")

    return {
        "activity": {
            "id": activity_id,
            "name": title,
            "description": description,
            "name_translations": {"en": title},
            "description_translations": {"en": description},
            "age_min": age_min,
            "age_max": age_max,
            "category_id": cat_id,
            "kind": kind,
            "facts": dict(FACTS_BY_KIND[kind]),
            "category_root_id": category.root_id,
            "category_name": cat_label,
            "category_name_translations": {
                "en": cat_label,
                "zh": category.label_zh,
                "zh-HK": category.label_zh,
            },
        },
        "organization": {
            "id": org_id,
            "name": f"{cat_label} Studio — {district_name}",
            "description": f"English-language {cat_label.lower()} provider in Hong Kong.",
            "name_translations": {
                "en": f"{cat_label} Studio — {district_name}",
            },
            "description_translations": {
                "en": (f"English-language {cat_label.lower()} provider in Hong Kong."),
            },
            "media_urls": ["https://placekitten.com/400/300"],
            "logo_media_url": "https://placekitten.com/120/120",
            "parent_verified": verified,
            "parent_verified_at": VERIFIED_AT if verified else None,
        },
        "location": {
            "id": location_id,
            "area_id": str(hood.id),
            "region_area_id": region_id,
            "address": f"1 Example Road, {hood.name}, {district_name}, Hong Kong",
            "lat": f"{hood.lat:.4f}",
            "lng": f"{hood.lng:.4f}",
        },
        "pricing": {
            "pricing_type": pricing_type,
            "amount": float(Decimal(str(amount))),
            "currency": "HKD",
            "sessions_count": sessions_count,
            "free_trial_class_offered": pricing_type == "per_class",
        },
        "schedule": _schedule(kind, day, start, end),
        "_sort": {
            "day_of_week_utc": day,
            "start_minutes_utc": start,
            "schedule_id": schedule_id,
        },
        "_meta": {
            "district_name": district_name,
            "region_label": region_label,
        },
    }


def generate() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    hood_counts: dict[str, int] = {}
    prices = {row[0]: row for row in PRICING_TYPES}
    for category in CATEGORIES:
        for age_key, _search_age, age_min, age_max in AGE_GROUPS:
            if age_key not in category.age_keys:
                continue
            for district_index, (district_name, region_id) in enumerate(DISTRICTS):
                for price_key in category.pricing_types:
                    pricing_type, pricing_label, amount, sessions = prices[price_key]
                    for variant, (day, start, end) in enumerate(SCHEDULE_VARIANTS):
                        hood_index = hood_counts.get(district_name, 0)
                        hood_counts[district_name] = hood_index + 1
                        items.append(
                            _build_item(
                                category=category,
                                kind=category.kinds[variant],
                                age_key=age_key,
                                age_min=age_min,
                                age_max=age_max,
                                district_name=district_name,
                                region_id=region_id,
                                verified=district_index % VERIFIED_EVERY == 0,
                                pricing_type=pricing_type,
                                pricing_label=pricing_label,
                                amount=amount,
                                sessions_count=sessions,
                                variant=variant,
                                day=day,
                                start=start,
                                end=end,
                                hood_index=hood_index,
                            )
                        )

    expected = (
        sum(
            len(category.pricing_types) * len(category.age_keys)
            for category in CATEGORIES
        )
        * len(DISTRICTS)
        * len(SCHEDULE_VARIANTS)
    )
    if len(items) != expected:
        raise RuntimeError(f"Expected {expected} items, got {len(items)}")
    if len(items) < 3000:
        raise RuntimeError(f"Item count {len(items)} is below 3000")
    covered = {item["location"]["area_id"] for item in items}
    missing = [item.name for item in NEIGHBOURHOODS if str(item.id) not in covered]
    if missing:
        raise RuntimeError(f"Neighbourhoods missing from staging: {missing}")

    return {
        "version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "locale": "en",
        "region": "HK",
        "meta": {
            "area_descendants": _build_area_descendants(),
            "category_descendants": _build_category_descendants(),
            "item_count": len(items),
        },
        "items": items,
    }


def main() -> None:
    payload = generate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {payload['meta']['item_count']} items to {OUTPUT}")


if __name__ == "__main__":
    main()
