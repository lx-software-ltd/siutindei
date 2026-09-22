"""Search API handler integration with the staging fixture backend."""

from __future__ import annotations

import time

import pytest

from app.api.search import fetch_search_response
from app.db.queries import ActivitySearchFilters
from app.services import staging_search_store

from staging_search_acceptance import (
    DISCOVERY_HOME_SEARCH_LIMIT,
    DISCOVERY_LOAD_BUDGET_SECONDS,
    MIN_PUBLIC_LISTINGS,
)


@pytest.fixture(autouse=True)
def enable_staging_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGING_SEARCH_DATA_ENABLED", "true")
    staging_search_store._FIXTURE_CACHE = None
    staging_search_store._SORTED_PUBLISHED_ITEMS = None


def test_fetch_search_response_returns_at_least_ten_listings() -> None:
    response = fetch_search_response(ActivitySearchFilters(limit=MIN_PUBLIC_LISTINGS))
    assert len(response.items) >= MIN_PUBLIC_LISTINGS


def test_fetch_search_response_discovery_home_within_budget() -> None:
    """Benchmark: same listing count as public discovery home fetch."""

    fetch_search_response(ActivitySearchFilters(limit=1))

    started = time.perf_counter()
    response = fetch_search_response(
        ActivitySearchFilters(limit=DISCOVERY_HOME_SEARCH_LIMIT),
    )
    elapsed = time.perf_counter() - started

    assert len(response.items) >= MIN_PUBLIC_LISTINGS
    assert elapsed < DISCOVERY_LOAD_BUDGET_SECONDS
