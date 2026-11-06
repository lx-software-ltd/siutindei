"""Search text match and card payload against PostgreSQL."""

from __future__ import annotations

import json

from app.api.schemas import ActivitySearchResponseSchema, dump_search_response
from app.api.search import map_row_to_result
from app.db.models import Activity, ActivityScheduleEntry
from app.db.queries import ActivitySearchFilters, build_search_query


def test_text_query_matches_names_not_descriptions(
    db_session,
    sample_activity,
    sample_organization,
    sample_pricing,
    sample_schedule,
) -> None:
    sample_activity.name_translations = {"zh": "游泳班"}
    sample_activity.description = "heated pool only"
    sample_organization.name = "Harbour Club"
    db_session.flush()

    def names(text_query: str) -> list[str]:
        rows = db_session.execute(
            build_search_query(ActivitySearchFilters(text_query=text_query, limit=10))
        ).all()
        return [row._mapping[Activity].name for row in rows]

    assert names("游泳") == ["Swimming Class"]
    assert names("HARBOUR") == ["Swimming Class"]
    assert names("heated") == []


def test_card_view_omits_heavy_fields_and_stays_under_900_bytes(
    db_session,
    sample_activity,
    sample_organization,
    sample_pricing,
    sample_schedule,
) -> None:
    sample_activity.description = "A long activity description. " * 40
    sample_organization.description = "A long organization description. " * 40
    sample_organization.place_id = "ChIJexampleplace"
    sample_organization.media_urls = [
        "https://cdn.example/one.jpg",
        "https://cdn.example/two.jpg",
    ]
    sample_schedule.entries.append(
        ActivityScheduleEntry(
            day_of_week_utc=3,
            start_minutes_utc=900,
            end_minutes_utc=960,
        )
    )
    db_session.flush()
    db_session.refresh(sample_schedule)

    row = db_session.execute(build_search_query(ActivitySearchFilters(limit=10))).one()
    card = map_row_to_result(row, {}, view="card")
    full = map_row_to_result(row, {}, view="full")
    card_item = dump_search_response(
        ActivitySearchResponseSchema(items=[card]),
        view="card",
    )["items"][0]
    full_item = dump_search_response(
        ActivitySearchResponseSchema(items=[full]),
        view="full",
    )["items"][0]

    assert "description" not in card_item["activity"]
    assert "description_translations" not in card_item["activity"]
    assert "description" not in card_item["organization"]
    assert "description_translations" not in card_item["organization"]
    assert "manager_id" not in card_item["organization"]
    assert "place_id" not in card_item["organization"]
    assert card_item["organization"]["media_urls"] == ["https://cdn.example/one.jpg"]
    assert len(card_item["schedule"]["weekly_entries"]) == 1
    assert card_item["schedule"]["weekly_entries"][0]["day_of_week_utc"] == 1
    assert full_item["activity"]["description"]
    assert "manager_id" not in full_item["organization"]
    assert len(full_item["schedule"]["weekly_entries"]) == 2
    assert "age_min" in card_item["activity"]
    assert "lat" in card_item["location"]
    encoded = json.dumps(card_item, default=str, separators=(",", ":")).encode()
    assert len(encoded) < 900


def test_full_view_keeps_a_unique_description_tagged_template(
    db_session,
    sample_activity,
    sample_organization,
    sample_pricing,
    sample_schedule,
) -> None:
    sample_organization.description = "Saturday art class for children in the harbour."
    sample_organization.description_source = "template"
    sample_organization.description_translations = {
        "zh": "南區嘅幼兒或興趣班，適合小朋友同家庭。",
    }
    sample_activity.description = "Lane swimming for beginners."
    db_session.flush()
    row = db_session.execute(build_search_query(ActivitySearchFilters(limit=10))).one()
    full = map_row_to_result(row, {}, view="full")
    card = map_row_to_result(row, {}, view="card")
    assert full.organization.description == sample_organization.description
    assert full.organization.description_translations.get("en") == (
        sample_organization.description
    )
    assert "zh" not in full.organization.description_translations
    assert full.activity.description == "Lane swimming for beginners."
    assert card.organization.description is None
    assert card.activity.description is None


def test_full_view_hides_lcsd_venue_filler(
    db_session,
    sample_activity,
    sample_organization,
    sample_pricing,
    sample_schedule,
) -> None:
    sample_organization.description = (
        "Harbour Park is a indoor family venue in Yau Tsim Mong "
        "for children and families."
    )
    sample_organization.description_source = "template"
    sample_activity.description = "Lane swimming for beginners."
    db_session.flush()
    row = db_session.execute(build_search_query(ActivitySearchFilters(limit=10))).one()
    full = map_row_to_result(row, {}, view="full")
    assert full.organization.description is None
    assert full.activity.description is None


def test_full_view_hides_import_boilerplate(
    db_session,
    sample_activity,
    sample_organization,
    sample_pricing,
    sample_schedule,
) -> None:
    sample_organization.description = (
        "Harbour Club is a class or early-years centre in CENTRAL "
        "for children and families."
    )
    sample_organization.description_source = "template"
    sample_activity.description = "Lane swimming for beginners."
    db_session.flush()
    row = db_session.execute(build_search_query(ActivitySearchFilters(limit=10))).one()
    full = map_row_to_result(row, {}, view="full")
    assert full.organization.description is None
    assert full.activity.description is None


def test_blank_template_description_still_hides_activity_copy(
    db_session,
    sample_activity,
    sample_organization,
    sample_pricing,
    sample_schedule,
) -> None:
    sample_organization.description = "   "
    sample_organization.description_source = "template"
    sample_activity.description = "Lane swimming for beginners."
    db_session.flush()
    row = db_session.execute(build_search_query(ActivitySearchFilters(limit=10))).one()
    full = map_row_to_result(row, {}, view="full")
    assert full.organization.description is None
    assert full.activity.description is None
