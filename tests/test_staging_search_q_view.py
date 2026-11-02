"""Staging search applies q and view without requiring the fixture file."""

from __future__ import annotations

from app.api.schemas import ActivitySearchResponseSchema
from app.api.schemas import dump_search_response
from app.db.queries import ActivitySearchFilters
from app.services.staging_search_store import _matches
from app.services.staging_search_store import _to_schema


def _row() -> dict:
    return {
        "activity": {
            "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "name": "Swimming Class",
            "description": "heated pool only",
            "name_translations": {"zh": "游泳班"},
            "description_translations": {"zh": "很長的描述"},
            "age_min": 5,
            "age_max": 12,
            "category_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        },
        "organization": {
            "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "name": "Harbour Club",
            "description": "organization story",
            "name_translations": {"zh": "海港會"},
            "description_translations": {"zh": "機構介紹"},
            "manager_id": "manager-1",
            "media_urls": [
                "https://cdn.example/one.jpg",
                "https://cdn.example/two.jpg",
            ],
            "place_id": "ChIJexample",
        },
        "location": {
            "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "area_id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
            "region_area_id": None,
            "address": "1 Road",
            "lat": "22.2",
            "lng": "114.1",
        },
        "pricing": {
            "pricing_type": "per_class",
            "amount": "150.00",
            "currency": "HKD",
        },
        "schedule": {
            "schedule_type": "weekly",
            "languages": ["en"],
            "weekly_entries": [
                {
                    "day_of_week_utc": 3,
                    "start_minutes_utc": 900,
                    "end_minutes_utc": 960,
                },
                {
                    "day_of_week_utc": 1,
                    "start_minutes_utc": 600,
                    "end_minutes_utc": 660,
                },
            ],
        },
    }


def test_staging_matches_when_q_and_view_are_absent() -> None:
    assert _matches(_row(), ActivitySearchFilters(), {}, None)


def test_staging_q_matches_names_not_descriptions() -> None:
    row = _row()
    assert _matches(row, ActivitySearchFilters(text_query="游泳"), {}, None)
    assert _matches(row, ActivitySearchFilters(text_query="harbour"), {}, None)
    assert not _matches(row, ActivitySearchFilters(text_query="heated"), {}, None)


def test_staging_card_trims_and_full_keeps_entry_order() -> None:
    row = _row()
    full = _to_schema(row)
    card = _to_schema(row, "card")
    assert full.activity.description == "heated pool only"
    assert [entry.day_of_week_utc for entry in full.schedule.weekly_entries] == [3, 1]
    assert card.activity.description is None
    assert card.organization.description is None
    assert card.organization.media_urls == ["https://cdn.example/one.jpg"]
    assert len(card.schedule.weekly_entries) == 1
    assert card.schedule.weekly_entries[0].day_of_week_utc == 1
    dumped = dump_search_response(
        ActivitySearchResponseSchema(items=[card]),
        view="card",
    )["items"][0]
    assert "manager_id" not in dumped["organization"]
    assert "place_id" not in dumped["organization"]
    assert "description" not in dumped["activity"]
