"""Tests for staging JSON search store."""

from __future__ import annotations

from uuid import UUID

import pytest
from app.db.queries import ActivitySearchFilters
from app.services import staging_search_store


@pytest.fixture(autouse=True)
def enable_staging_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGING_SEARCH_DATA_ENABLED", "true")
    staging_search_store._FIXTURE_CACHE = None
    staging_search_store._SORTED_PUBLISHED_ITEMS = None


def test_staging_fixture_has_at_least_3000_items() -> None:
    payload = staging_search_store._load_fixture()
    assert payload["meta"]["item_count"] >= 3000


def test_filter_by_category_and_age() -> None:
    filters = ActivitySearchFilters(
        age=4,
        category_ids=[UUID("c1111111-1111-1111-1111-111111111201")],
        limit=10,
    )
    response = staging_search_store.fetch_staging_search_response(filters)
    assert len(response.items) == 10
    for item in response.items:
        assert item.activity.category_id == "c1111111-1111-1111-1111-111111111201"
        assert item.activity.age_min is not None
        assert item.activity.age_max is not None
        assert item.activity.age_min <= 4 <= item.activity.age_max


def test_filter_by_hk_region_area_id() -> None:
    filters = ActivitySearchFilters(
        area_id=UUID("a1111111-1111-1111-1111-111111111102"),
        limit=5,
    )
    response = staging_search_store.fetch_staging_search_response(filters)
    assert len(response.items) == 5
    for item in response.items:
        assert item.location.region_area_id == "a1111111-1111-1111-1111-111111111102"


def test_pagination_cursor() -> None:
    first = staging_search_store.fetch_staging_search_response(
        ActivitySearchFilters(limit=2),
    )
    assert first.next_cursor is not None
    second = staging_search_store.fetch_staging_search_response(
        ActivitySearchFilters(limit=2, cursor=_decode(first.next_cursor)),
    )
    assert len(second.items) == 2
    assert first.items[0].activity.id != second.items[0].activity.id


def _decode(cursor: str):
    from app.api.search_page import parse_cursor as _parse_cursor

    return _parse_cursor(cursor)


def _write_fixture(tmp_path, monkeypatch, items):
    import json

    path = tmp_path / "fixture.json"
    path.write_text(
        json.dumps({"meta": {"item_count": len(items)}, "items": items}),
        encoding="utf-8",
    )
    monkeypatch.setenv("STAGING_SEARCH_DATA_PATH", str(path))
    staging_search_store._FIXTURE_CACHE = None
    staging_search_store._SORTED_PUBLISHED_ITEMS = None


def _item(index: int, *, org: str, pricing: dict, entry: tuple[int, int]) -> dict:
    return {
        "activity": {
            "id": f"00000000-0000-0000-0000-00000000000{index}",
            "name": f"Class {index}",
            "name_translations": {},
            "age_min": 3,
            "age_max": 6,
            "category_id": "c1111111-1111-1111-1111-111111111201",
        },
        "organization": {
            "id": org,
            "name": "Example Club",
            "name_translations": {},
            "media_urls": [],
            "logo_media_url": None,
            "parent_verified": index == 1,
            "contact": {"website": "https://example.com"},
            "rating": {"count": 3, "average_stars": "4.7"},
            "reviews": [
                {
                    "id": "r1",
                    "stars": 5,
                    "description": "Great",
                    "labels": [],
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ],
        },
        "location": {
            "id": f"10000000-0000-0000-0000-00000000000{index}",
            "area_id": "a1111111-1111-1111-1111-111111111102",
            "name": "Studio",
            "address": "1 Example Road",
        },
        "pricing": {"currency": "HKD", **pricing},
        "schedule": {
            "schedule_type": "weekly",
            "languages": ["en"],
            "weekly_entries": [
                {
                    "day_of_week_utc": entry[0],
                    "start_minutes_utc": entry[1],
                    "end_minutes_utc": (entry[1] + 60) % 1440,
                }
            ],
        },
    }


_ORG_A = "20000000-0000-0000-0000-00000000000a"
_ORG_B = "20000000-0000-0000-0000-00000000000b"


@pytest.fixture
def small_fixture(tmp_path, monkeypatch):
    _write_fixture(
        tmp_path,
        monkeypatch,
        [
            _item(
                1,
                org=_ORG_A,
                pricing={
                    "pricing_type": "per_sessions",
                    "amount": 2400,
                    "sessions_count": 8,
                    "free_trial_class_offered": True,
                },
                entry=(1, 120),
            ),
            _item(
                2,
                org=_ORG_A,
                pricing={"pricing_type": "per_class", "amount": 150},
                entry=(5, 1380),
            ),
            _item(
                3,
                org=_ORG_B,
                pricing={"pricing_type": "per_month", "amount": 900},
                entry=(2, 120),
            ),
        ],
    )
    yield
    staging_search_store._FIXTURE_CACHE = None
    staging_search_store._SORTED_PUBLISHED_ITEMS = None


def _ids(response) -> list[str]:
    return [item.activity.id[-1] for item in response.items]


def test_staging_new_filters_match_the_database_rules(small_fixture) -> None:
    fetch = staging_search_store.fetch_staging_search_response
    assert _ids(fetch(ActivitySearchFilters(org_ids=(UUID(_ORG_B),)))) == ["3"]
    assert _ids(fetch(ActivitySearchFilters(free_trial=True))) == ["1"]
    assert _ids(fetch(ActivitySearchFilters(days_of_week_hkt=(6,)))) == ["2"]
    from decimal import Decimal

    assert _ids(fetch(ActivitySearchFilters(class_price_max=Decimal(300)))) == [
        "1",
        "2",
    ]


def test_staging_price_sort_total_and_detail_fields(small_fixture) -> None:
    fetch = staging_search_store.fetch_staging_search_response
    first = fetch(ActivitySearchFilters(sort="price", limit=2, include_total=True))
    assert _ids(first) == ["2", "1"]
    assert first.total == 3
    second = fetch(
        ActivitySearchFilters(sort="price", limit=2, cursor=_decode(first.next_cursor))
    )
    assert _ids(second) == ["3"]
    assert second.total is None

    detail = fetch(
        ActivitySearchFilters(activity_id=UUID("00000000-0000-0000-0000-000000000001"))
    ).items[0]
    assert detail.organization.parent_verified is True
    assert detail.organization.contact is not None
    assert detail.organization.rating is not None
    assert detail.organization.rating.count == 3
    assert len(detail.organization.reviews) == 1
    assert detail.location.name == "Studio"

    listed = fetch(ActivitySearchFilters(view="card")).items[0]
    assert listed.organization.contact is None
    assert listed.organization.reviews == []


_TOPIC = "c1111111-1111-1111-1111-111111111302"
_PLACES_ROOT = "c1111111-1111-1111-1111-111111111401"
_PLAYGROUND = "c1111111-1111-1111-1111-111111111411"


@pytest.fixture
def kinds_fixture(tmp_path, monkeypatch):
    old = _item(
        1,
        org=_ORG_A,
        pricing={"pricing_type": "per_class", "amount": 150},
        entry=(1, 120),
    )
    camp = _item(
        2,
        org=_ORG_A,
        pricing={"pricing_type": "per_day", "amount": 400},
        entry=(2, 120),
    )
    camp["activity"].update(
        kind="camp",
        age_min=8,
        age_max=12,
        category_id=_TOPIC,
        category_root_id=_TOPIC,
        category_name="Sports",
        category_name_translations={"en": "Sports", "zh-HK": "運動"},
        facts={"lunch_included": True},
    )
    place = _item(
        3,
        org=_ORG_B,
        pricing={"pricing_type": "free", "amount": 0},
        entry=(3, 120),
    )
    place["activity"].update(
        kind="place",
        age_min=0,
        age_max=18,
        category_id=_PLAYGROUND,
        category_root_id=_PLACES_ROOT,
        category_name="Playground and park",
        category_name_translations={"en": "Playground and park"},
        facts={"toilets": True, "shade": False},
    )
    place["organization"].update(
        parent_verified=True, parent_verified_at="2026-11-01T02:00:00Z"
    )
    _write_fixture(tmp_path, monkeypatch, [old, camp, place])
    yield
    staging_search_store._FIXTURE_CACHE = None
    staging_search_store._SORTED_PUBLISHED_ITEMS = None


def test_staging_kind_age_range_and_verified_filters(kinds_fixture) -> None:
    fetch = staging_search_store.fetch_staging_search_response
    assert _ids(fetch(ActivitySearchFilters())) == ["1", "2", "3"]
    assert _ids(fetch(ActivitySearchFilters(kinds=("class",)))) == ["1"]
    assert _ids(fetch(ActivitySearchFilters(kinds=("camp", "place")))) == ["2", "3"]
    assert _ids(fetch(ActivitySearchFilters(age_min=6, age_max=7))) == ["1", "3"]
    assert _ids(fetch(ActivitySearchFilters(age_min=12))) == ["2", "3"]
    assert _ids(fetch(ActivitySearchFilters(age_max=2))) == ["3"]
    assert _ids(fetch(ActivitySearchFilters(verified_only=True))) == ["1", "3"]


def test_staging_returns_kind_category_and_checked_date(kinds_fixture) -> None:
    fetch = staging_search_store.fetch_staging_search_response
    by_id = {item.activity.id[-1]: item for item in fetch(ActivitySearchFilters()).items}

    old = by_id["1"].activity
    assert old.kind == "class"
    assert old.facts == {}
    assert old.category_root_id is None
    assert old.category_name is None

    place = by_id["3"]
    assert place.activity.kind == "place"
    assert place.activity.facts == {"toilets": True, "shade": False}
    assert place.activity.category_root_id == _PLACES_ROOT
    assert place.activity.category_name == "Playground and park"
    assert place.organization.parent_verified_at is not None
    assert by_id["2"].activity.category_name_translations["zh-HK"] == "運動"
    assert by_id["2"].organization.parent_verified_at is None
