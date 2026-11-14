"""The staging fixture generator emits kinds, topics, and fixed-root leaves."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from app.db.models.category_suggestion import FIXED_ROOT_KINDS, WIZARD_GROUP_IDS
from app.db.queries import ActivitySearchFilters
from app.db.search_conditions import hong_kong_day
from app.services import staging_search_store
from app.services.listing_kinds import FACT_KEYS, KINDS
from app.services.schedule_dates import hong_kong_weekdays_between

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "codegen"
    / "generate_activity_search_staging.py"
)


@pytest.fixture(scope="module")
def payload() -> dict:
    spec = importlib.util.spec_from_file_location("staging_generator", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate()


def test_every_topic_and_fixed_kind_is_present(payload) -> None:
    activities = [item["activity"] for item in payload["items"]]
    roots = {UUID(activity["category_root_id"]) for activity in activities}
    assert WIZARD_GROUP_IDS <= roots
    listed_fixed_roots = {
        root
        for root, kind in FIXED_ROOT_KINDS.items()
        if kind in {"place", "preschool"}
    }
    assert listed_fixed_roots <= roots
    kinds = Counter(activity["kind"] for activity in activities)
    assert set(kinds) == {"class", "camp", "place", "preschool"}
    assert payload["meta"]["item_count"] == len(payload["items"]) >= 3000


def test_items_match_the_search_response_shape(payload) -> None:
    for item in payload["items"]:
        activity = item["activity"]
        root = UUID(activity["category_root_id"])
        assert activity["kind"] in KINDS
        assert set(activity["facts"]) <= set(FACT_KEYS[activity["kind"]])
        assert activity["category_name"]
        assert activity["category_name_translations"]["en"] == activity["category_name"]
        if root in WIZARD_GROUP_IDS:
            assert activity["kind"] in {"class", "camp"}
            assert activity["category_id"] == activity["category_root_id"]
        else:
            assert activity["kind"] == FIXED_ROOT_KINDS[root]
            assert activity["category_id"] != activity["category_root_id"]
        organization = item["organization"]
        if organization["parent_verified"]:
            assert organization["parent_verified_at"]
        else:
            assert organization["parent_verified_at"] is None


def test_category_descendants_reach_the_fixed_root_leaves(payload) -> None:
    descendants = payload["meta"]["category_descendants"]
    for item in payload["items"]:
        activity = item["activity"]
        assert activity["category_id"] in descendants[activity["category_root_id"]]


def test_staging_store_serves_the_generated_fixture(
    payload, tmp_path, monkeypatch
) -> None:
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("STAGING_SEARCH_DATA_ENABLED", "true")
    monkeypatch.setenv("STAGING_SEARCH_DATA_PATH", str(path))
    staging_search_store._FIXTURE_CACHE = None
    staging_search_store._SORTED_PUBLISHED_ITEMS = None
    try:
        places_root = next(
            key for key, kind in FIXED_ROOT_KINDS.items() if kind == "place"
        )
        response = staging_search_store.fetch_staging_search_response(
            ActivitySearchFilters(
                category_ids=[places_root],
                kinds=("place",),
                verified_only=True,
                limit=5,
            )
        )
        assert len(response.items) == 5
        for item in response.items:
            assert item.activity.kind == "place"
            assert item.activity.category_root_id == str(places_root)
            assert item.organization.parent_verified is True
    finally:
        staging_search_store._FIXTURE_CACHE = None
        staging_search_store._SORTED_PUBLISHED_ITEMS = None


def test_camp_rows_carry_one_dated_session(payload, tmp_path, monkeypatch) -> None:
    camps = [item for item in payload["items"] if item["activity"]["kind"] == "camp"]
    assert camps
    for item in camps:
        schedule = item["schedule"]
        starts_on = date.fromisoformat(schedule["starts_on"])
        ends_on = date.fromisoformat(schedule["ends_on"])
        weekdays = hong_kong_weekdays_between(starts_on, ends_on)
        for entry in schedule["weekly_entries"]:
            assert (
                hong_kong_day(entry["day_of_week_utc"], entry["start_minutes_utc"])
                in weekdays
            )
    for item in payload["items"]:
        if item["activity"]["kind"] != "camp":
            assert "starts_on" not in item["schedule"]

    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("STAGING_SEARCH_DATA_ENABLED", "true")
    monkeypatch.setenv("STAGING_SEARCH_DATA_PATH", str(path))
    staging_search_store._FIXTURE_CACHE = None
    staging_search_store._SORTED_PUBLISHED_ITEMS = None
    session_start = date.fromisoformat(camps[0]["schedule"]["starts_on"])
    try:
        during = staging_search_store.fetch_staging_search_response(
            ActivitySearchFilters(
                kinds=("camp",), date_from=session_start, date_to=session_start
            )
        )
        assert during.items
        assert during.items[0].schedule.starts_on == camps[0]["schedule"]["starts_on"]
        after = staging_search_store.fetch_staging_search_response(
            ActivitySearchFilters(
                kinds=("camp",), today=session_start + timedelta(days=30)
            )
        )
        assert after.items == []
    finally:
        staging_search_store._FIXTURE_CACHE = None
        staging_search_store._SORTED_PUBLISHED_ITEMS = None
