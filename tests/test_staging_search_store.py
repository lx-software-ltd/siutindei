"""Tests for staging JSON search store."""

from __future__ import annotations

import os
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
        category_ids=[UUID("c1111111-1111-1111-1111-111111111102")],
        limit=10,
    )
    response = staging_search_store.fetch_staging_search_response(filters)
    assert len(response.items) == 10
    for item in response.items:
        assert item.activity.category_id == "c1111111-1111-1111-1111-111111111102"
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
    from app.api.search import _parse_cursor

    return _parse_cursor(cursor)
