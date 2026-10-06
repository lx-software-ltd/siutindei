#!/usr/bin/env python3
"""Generate staging activity search fixture (~3000 HK, English-only rows)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "shared" / "fixtures" / "activity_search_staging.json"

NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
MANAGER_ID = "00000000-0000-0000-0000-000000000001"

HK_ISLAND_REGION = "a1111111-1111-1111-1111-111111111101"
KOWLOON_REGION = "a1111111-1111-1111-1111-111111111102"
NEW_TERRITORIES_REGION = "a1111111-1111-1111-1111-111111111103"
ISLANDS_REGION = "a1111111-1111-1111-1111-111111111104"

CATEGORIES: list[tuple[str, str]] = [
    ("c1111111-1111-1111-1111-111111111201", "Early years and schools"),
    ("c1111111-1111-1111-1111-111111111202", "Learning and tutoring"),
    ("c1111111-1111-1111-1111-111111111203", "Arts and performance"),
    ("c1111111-1111-1111-1111-111111111204", "Sports and movement"),
    ("c1111111-1111-1111-1111-111111111205", "Play and outdoors"),
    ("c1111111-1111-1111-1111-111111111206", "Culture"),
    ("c1111111-1111-1111-1111-111111111207", "Community and support"),
]

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

SCHEDULE_VARIANTS: list[tuple[int, int, int]] = [
    (1, 600, 660),
    (3, 840, 900),
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
    for name, region_id in DISTRICTS:
        district_id = _district_id(name)
        by_region[region_id].append(district_id)
    descendants: dict[str, list[str]] = {}
    for region_id, district_ids in by_region.items():
        descendants[region_id] = list(district_ids)
        for district_id in district_ids:
            descendants[district_id] = [district_id]
    return descendants


def _build_category_descendants() -> dict[str, list[str]]:
    """Wizard groups are stored directly on staging rows."""
    return {category_id: [category_id] for category_id, _label in CATEGORIES}


def _build_item(
    *,
    cat_id: str,
    cat_label: str,
    age_key: str,
    age_min: int,
    age_max: int,
    district_name: str,
    region_id: str,
    pricing_type: str,
    pricing_label: str,
    amount: float,
    sessions_count: int | None,
    variant: int,
    day: int,
    start: int,
    end: int,
) -> dict[str, Any]:
    district_id = _district_id(district_name)
    cell_key = f"{cat_id}:{age_key}:{district_name}:{pricing_type}:{variant}"
    activity_id = _uuid(f"siutindei.staging.activity.{cell_key}")
    org_id = _uuid(f"siutindei.staging.org.{cat_id}:{district_name}")
    location_id = _uuid(f"siutindei.staging.location.{district_name}")
    schedule_id = _uuid(f"siutindei.staging.schedule.{cell_key}")

    title = (
        f"{cat_label} in {district_name} "
        f"(ages {age_min}–{age_max}, {pricing_label})"
    )
    description = (
        f"Staging listing for {cat_label.lower()} in {district_name}, "
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
        },
        "organization": {
            "id": org_id,
            "name": f"{cat_label} Studio — {district_name}",
            "description": f"English-language {cat_label.lower()} provider in Hong Kong.",
            "name_translations": {
                "en": f"{cat_label} Studio — {district_name}",
            },
            "description_translations": {
                "en": (
                    f"English-language {cat_label.lower()} " f"provider in Hong Kong."
                ),
            },
            "manager_id": MANAGER_ID,
            "media_urls": ["https://placekitten.com/400/300"],
            "logo_media_url": "https://placekitten.com/120/120",
        },
        "location": {
            "id": location_id,
            "area_id": district_id,
            "region_area_id": region_id,
            "address": f"1 Example Road, {district_name}, Hong Kong",
            "lat": "22.3000",
            "lng": "114.1700",
        },
        "pricing": {
            "pricing_type": pricing_type,
            "amount": float(Decimal(str(amount))),
            "currency": "HKD",
            "sessions_count": sessions_count,
            "free_trial_class_offered": pricing_type == "per_class",
        },
        "schedule": {
            "schedule_type": "weekly",
            "weekly_entries": [
                {
                    "day_of_week_utc": day,
                    "start_minutes_utc": start,
                    "end_minutes_utc": end,
                }
            ],
            "languages": ["en"],
        },
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
    for cat_id, cat_label in CATEGORIES:
        for age_key, _search_age, age_min, age_max in AGE_GROUPS:
            for district_name, region_id in DISTRICTS:
                for pricing_type, pricing_label, amount, sessions in PRICING_TYPES:
                    for variant, (day, start, end) in enumerate(SCHEDULE_VARIANTS):
                        items.append(
                            _build_item(
                                cat_id=cat_id,
                                cat_label=cat_label,
                                age_key=age_key,
                                age_min=age_min,
                                age_max=age_max,
                                district_name=district_name,
                                region_id=region_id,
                                pricing_type=pricing_type,
                                pricing_label=pricing_label,
                                amount=amount,
                                sessions_count=sessions,
                                variant=variant,
                                day=day,
                                start=start,
                                end=end,
                            )
                        )

    expected = (
        len(CATEGORIES)
        * len(AGE_GROUPS)
        * len(DISTRICTS)
        * len(PRICING_TYPES)
        * len(SCHEDULE_VARIANTS)
    )
    if len(items) != expected:
        raise RuntimeError(f"Expected {expected} items, got {len(items)}")
    if len(items) < 3000:
        raise RuntimeError(f"Item count {len(items)} is below 3000")

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
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {payload['meta']['item_count']} items to {OUTPUT}")


if __name__ == "__main__":
    main()
