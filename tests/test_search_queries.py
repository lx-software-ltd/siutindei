"""Tests for search query building."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from sqlalchemy.dialects import postgresql  # noqa: E402

from app.db.queries import ActivitySearchCursor  # noqa: E402
from app.db.queries import ActivitySearchFilters  # noqa: E402
from app.db.queries import build_search_query  # noqa: E402
from app.db.queries import validate_filters  # noqa: E402


def test_validate_filters_rejects_invalid_minutes() -> None:
    """Ensure start_minutes_utc is less than end_minutes_utc."""

    filters = ActivitySearchFilters(start_minutes_utc=600, end_minutes_utc=540)
    with pytest.raises(ValueError, match="start_minutes_utc"):
        validate_filters(filters)


def test_build_search_query_includes_wrap_conditions() -> None:
    """Ensure wrapped schedules are considered for time filters."""

    filters = ActivitySearchFilters(start_minutes_utc=480, end_minutes_utc=600)
    query = build_search_query(filters)
    where_clause = str(query)
    wrap_fragment = (
        "activity_schedule_entries.start_minutes_utc > "
        "activity_schedule_entries.end_minutes_utc"
    )
    assert wrap_fragment in where_clause


def test_build_search_query_sets_limit() -> None:
    """Ensure the query sets a limit."""

    filters = ActivitySearchFilters(limit=25)
    query = build_search_query(filters)
    assert query._limit_clause is not None


def test_build_search_query_filters_by_org_ids() -> None:
    """Ensure org-scoped partner keys restrict results by organization."""

    org_id = uuid4()
    filters = ActivitySearchFilters(org_ids=(org_id,))
    query = build_search_query(filters)
    where_clause = str(query.whereclause)
    assert "activities.org_id IN" in where_clause


def test_build_search_query_no_org_filter_by_default() -> None:
    """Ensure no organization filter is applied without org_ids."""

    filters = ActivitySearchFilters()
    query = build_search_query(filters)
    where_clause = str(query.whereclause)
    assert "activities.org_id IN" not in where_clause


def test_build_search_query_uses_distinct_on_first_entry() -> None:
    """The first entry per schedule is DISTINCT ON, not a window."""

    query = build_search_query(ActivitySearchFilters())
    sql = str(query.compile(dialect=postgresql.dialect())).lower()
    assert "distinct on (activity_schedule_entries.schedule_id)" in sql
    assert "row_number" not in sql
    assert "entry_rank" not in sql


def test_build_search_query_filters_text_on_names() -> None:
    """q matches names and name translation values."""

    query = build_search_query(ActivitySearchFilters(text_query="swim"))
    sql = str(query.compile(dialect=postgresql.dialect())).lower()
    assert "jsonb_each_text" in sql
    assert "ilike" in sql
    assert "name_translations" in sql


def test_build_search_query_applies_cursor() -> None:
    """Ensure the cursor filter is applied."""

    cursor_id = uuid4()
    cursor = ActivitySearchCursor(
        day_of_week_utc=2,
        start_minutes_utc=480,
        schedule_id=cursor_id,
    )
    filters = ActivitySearchFilters(cursor=cursor)
    query = build_search_query(filters)
    where_clause = str(query.whereclause)
    assert "activity_schedule.id" in where_clause


def _sql(filters: ActivitySearchFilters) -> str:
    query = build_search_query(filters)
    return str(query.compile(dialect=postgresql.dialect())).lower()


def test_build_search_query_filters_by_kind() -> None:
    assert "activities.kind in" in _sql(ActivitySearchFilters(kinds=("class", "camp")))
    assert "activities.kind in" not in _sql(ActivitySearchFilters())


def test_build_search_query_overlaps_age_range() -> None:
    sql = _sql(ActivitySearchFilters(age_min=6, age_max=11))
    assert "activities.age_range && int4range" in sql
    assert "activities.age_range &&" not in _sql(ActivitySearchFilters(age=4))


def test_build_search_query_limits_to_verified_organizations() -> None:
    verified = "organizations.parent_verified is true"
    assert _sql(ActivitySearchFilters(verified_only=True)).count(verified) == 2
    assert _sql(ActivitySearchFilters()).count(verified) == 1


def test_build_search_query_shows_eat_only_from_verified_organizations() -> None:
    eat_rule = (
        "(activities.kind != %(kind_1)s::varchar "
        "or organizations.parent_verified is true)"
    )
    assert eat_rule in _sql(ActivitySearchFilters())
    assert eat_rule in _sql(ActivitySearchFilters(kinds=("eat",)))


def test_validate_filters_allows_one_probe_row_above_the_page_limit() -> None:
    """The pager asks for limit + 1 rows; the request limit stays 200."""

    validate_filters(ActivitySearchFilters(limit=201))
    with pytest.raises(ValueError, match="limit"):
        validate_filters(ActivitySearchFilters(limit=202))
