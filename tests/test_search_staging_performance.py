"""Staging search performance acceptance tests."""

from __future__ import annotations

import time
from uuid import UUID

import pytest

from app.db.queries import ActivitySearchFilters
from app.services import staging_search_store

from staging_search_acceptance import (
    DISCOVERY_LOAD_BUDGET_SECONDS,
    MIN_PUBLIC_LISTINGS,
)


@pytest.fixture(autouse=True)
def enable_staging_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGING_SEARCH_DATA_ENABLED", "true")
    staging_search_store._FIXTURE_CACHE = None
    staging_search_store._SORTED_PUBLISHED_ITEMS = None


def test_staging_search_returns_ten_listings_within_budget() -> None:
    staging_search_store.fetch_staging_search_response(
        ActivitySearchFilters(limit=1),
    )

    started = time.perf_counter()
    response = staging_search_store.fetch_staging_search_response(
        ActivitySearchFilters(
            age=4,
            category_ids=[UUID("c1111111-1111-1111-1111-111111111102")],
            limit=MIN_PUBLIC_LISTINGS,
        ),
    )
    elapsed = time.perf_counter() - started

    assert len(response.items) == MIN_PUBLIC_LISTINGS
    assert elapsed < DISCOVERY_LOAD_BUDGET_SECONDS
