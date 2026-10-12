"""Compare shapes for catalog version 1."""

from app.services.catalog_version_shape import (
    activity_shape,
    file_matches_snapshot,
    location_shape,
    organization_shape,
    pricing_shape,
    schedule_shape,
)


def test_organization_shape_ignores_manager_and_blank_contact() -> None:
    shape = organization_shape(
        {
            "name": "  Harbour   Club ",
            "manager_id": "manager-sub",
            "description": "  ",
            "name_translations": {"zh": " 海港 "},
            "email": None,
        }
    )
    assert shape["name"] == "harbour club"
    assert "manager_id" not in shape
    assert shape["description"] is None
    assert shape["name_translations"] == {"zh": "海港"}
    assert shape["email"] is None


def test_activity_shape_uses_inclusive_age_not_category() -> None:
    from_range = activity_shape(
        {
            "name": "Swim",
            "age_range": "[5,13)",
            "category_id": "old-category",
            "source_category_name": "Swimming",
        }
    )
    from_bounds = activity_shape(
        {
            "name": " swim ",
            "age_min": 5,
            "age_max": 12,
            "category_id": "new-category",
            "source_category_name": "Swimming",
        }
    )
    assert from_range == from_bounds
    assert from_range["age_min"] == 5
    assert from_range["age_max"] == 12
    assert "category_id" not in from_range


def test_location_and_money_quantize() -> None:
    assert location_shape({"lat": "22.2826674", "lng": 114.158167})["lat"] == (
        "22.282667"
    )
    assert pricing_shape({"amount": "10", "currency": "HKD"})["amount"] == "10.00"


def test_schedule_shape_sorts_utc_slots() -> None:
    left = schedule_shape(
        {
            "languages": ["zh", "en"],
            "entries": [
                {
                    "day_of_week_utc": 2,
                    "start_minutes_utc": 60,
                    "end_minutes_utc": 120,
                },
                {
                    "day_of_week_utc": 1,
                    "start_minutes_utc": 0,
                    "end_minutes_utc": 30,
                },
            ],
        }
    )
    right = schedule_shape(
        {
            "languages": ["en", "zh"],
            "weekly_entries": [
                {
                    "day_of_week_utc": 1,
                    "start_minutes_utc": 0,
                    "end_minutes_utc": 30,
                },
                {
                    "day_of_week_utc": 2,
                    "start_minutes_utc": 60,
                    "end_minutes_utc": 120,
                },
            ],
        }
    )
    assert left == right


def test_omitted_file_field_matches_snapshot() -> None:
    snapshot = {
        "name": "Harbour Club",
        "description": "Original",
        "status": "operational",
        "email": "desk@example.com",
    }
    assert file_matches_snapshot(
        "organization",
        {"name": "Harbour Club", "description": "Original"},
        snapshot,
        {"name", "description"},
    )
    assert not file_matches_snapshot(
        "organization",
        {"name": "Harbour Club", "description": "Changed"},
        snapshot,
        {"name", "description"},
    )
