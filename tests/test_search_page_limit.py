"""A search page of the documented maximum, 200, loads."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.api.search import fetch_search_response
from app.db.queries import ActivitySearchCursor, ActivitySearchFilters


@pytest.fixture
def engine(monkeypatch, test_engine):
    monkeypatch.setattr("app.api.search.get_engine", lambda: test_engine)
    return test_engine


@pytest.mark.parametrize("include_incomplete", [False, True])
def test_limit_200_returns_a_page(engine, include_incomplete: bool) -> None:
    filters = ActivitySearchFilters(
        org_ids=(uuid4(),),
        limit=200,
        include_incomplete=include_incomplete,
    )
    assert fetch_search_response(filters).items == []


def test_limit_200_on_the_incomplete_phase_returns_a_page(engine) -> None:
    filters = ActivitySearchFilters(
        org_ids=(uuid4(),),
        limit=200,
        include_incomplete=True,
        cursor=ActivitySearchCursor(
            day_of_week_utc=0,
            start_minutes_utc=0,
            schedule_id=uuid4(),
            phase="incomplete",
        ),
    )
    assert fetch_search_response(filters).items == []
