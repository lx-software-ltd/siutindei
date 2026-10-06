"""Tests for search category and area tree filters."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID
from uuid import uuid4

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from app.db.queries import ActivitySearchFilters  # noqa: E402
from app.db.queries import build_search_query  # noqa: E402
from app.utils.parsers import parse_uuid_list  # noqa: E402


def test_parse_uuid_list_deduplicates() -> None:
    """Repeated category ids are parsed once."""

    category_id = str(uuid4())
    parsed = parse_uuid_list([category_id, category_id])
    assert len(parsed) == 1


def test_build_search_query_applies_category_filter() -> None:
    """Category ids appear in the generated SQL."""

    category_id = uuid4()
    filters = ActivitySearchFilters(category_ids=[category_id])
    query = build_search_query(filters)
    compiled = str(query)
    assert "activities.category_id" in compiled
    assert "activity_categories" in compiled
    assert "EXISTS" not in compiled.upper()


def test_wizard_group_search_sql_unions_legacy_roots() -> None:
    """An empty wizard group can still match the legacy roots."""

    group_id = UUID("c1111111-1111-1111-1111-111111111201")
    filters = ActivitySearchFilters(category_ids=[group_id])
    compiled = str(build_search_query(filters)).upper()
    assert "EXISTS" in compiled


def test_staging_match_uses_category_descendants_when_present() -> None:
    from app.services.staging_search_store import _matches

    parent = uuid4()
    child = uuid4()
    item = {
        "activity": {
            "id": str(uuid4()),
            "category_id": str(child),
            "age_min": 5,
            "age_max": 12,
        },
        "location": {},
        "pricing": {"pricing_type": "free", "amount": 0},
        "schedule": {"schedule_type": "weekly", "languages": []},
    }
    filters = ActivitySearchFilters(category_ids=[parent])
    assert _matches(
        item,
        filters,
        {},
        {str(parent): [str(parent), str(child)]},
    )
    assert not _matches(item, filters, {}, None)


def test_build_search_query_applies_area_tree_filter() -> None:
    """Area id uses a recursive geographic area subquery."""

    filters = ActivitySearchFilters(area_id=uuid4())
    query = build_search_query(filters)
    where_clause = str(query.whereclause)
    assert "geographic_areas" in where_clause
