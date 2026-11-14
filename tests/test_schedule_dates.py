"""Dated schedule sessions in the admin schedule resource."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range

from app.api.admin_resource_schedule import (
    _create_schedule,
    _serialize_schedule,
    _update_schedule,
)
from app.api.admin_imports_export import serialize_export_schedule
from app.api.admin_imports_schedule import upsert_schedule
from app.db.models import (
    Activity,
    ActivitySchedule,
    ActivityScheduleEntry,
    Location,
    Organization,
    ScheduleType,
)
from app.db.repositories import ActivityScheduleRepository
from app.exceptions import ValidationError
from app.services.catalog_version_payload import schedule_payload
from app.services.catalog_version_shape import build_shape
from app.services.org_merge import merge_organizations
from app.services.schedule_dates import hong_kong_weekdays_between

HK_MONDAY_9AM = {"day_of_week_utc": 1, "start_minutes_utc": 60, "end_minutes_utc": 420}
HK_SUNDAY_9AM = {"day_of_week_utc": 0, "start_minutes_utc": 60, "end_minutes_utc": 420}
HK_MONDAY_7AM = {
    "day_of_week_utc": 0,
    "start_minutes_utc": 1380,
    "end_minutes_utc": 120,
}


def _body(activity, location, **overrides) -> dict:
    body = {
        "activity_id": str(activity.id),
        "location_id": str(location.id),
        "languages": ["en"],
        "weekly_entries": [HK_MONDAY_9AM],
        "starts_on": "2026-07-20",
        "ends_on": "2026-07-25",
    }
    body.update(overrides)
    return body


def _create(db_session, body):
    repo = ActivityScheduleRepository(db_session)
    schedule = _create_schedule(repo, body)
    db_session.add(schedule)
    db_session.flush()
    return schedule


def test_weekdays_between_uses_sunday_zero() -> None:
    assert hong_kong_weekdays_between(date(2026, 7, 20), date(2026, 7, 20)) == {1}
    assert hong_kong_weekdays_between(date(2026, 7, 20), date(2026, 7, 25)) == {
        1,
        2,
        3,
        4,
        5,
        6,
    }
    assert len(hong_kong_weekdays_between(date(2026, 7, 1), date(2026, 7, 31))) == 7


def test_create_returns_the_dates(db_session, sample_activity, sample_location) -> None:
    schedule = _create(db_session, _body(sample_activity, sample_location))

    payload = _serialize_schedule(schedule)
    assert payload["starts_on"] == "2026-07-20"
    assert payload["ends_on"] == "2026-07-25"


def test_undated_schedule_returns_null_dates(
    db_session, sample_activity, sample_location
) -> None:
    body = _body(sample_activity, sample_location)
    body.pop("starts_on")
    body.pop("ends_on")
    schedule = _create(db_session, body)

    payload = _serialize_schedule(schedule)
    assert payload["starts_on"] is None
    assert payload["ends_on"] is None


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"ends_on": None}, "ends_on"),
        ({"starts_on": None}, "starts_on"),
        ({"ends_on": "2026-07-19"}, "ends_on"),
        ({"starts_on": "20/07/2026"}, "starts_on"),
        ({"ends_on": 20260725}, "ends_on"),
    ],
)
def test_rejects_bad_dates(
    db_session, sample_activity, sample_location, overrides, field
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _create(db_session, _body(sample_activity, sample_location, **overrides))
    assert exc_info.value.field == field


def test_rejects_a_weekday_outside_the_session(
    db_session, sample_activity, sample_location
) -> None:
    body = _body(
        sample_activity,
        sample_location,
        weekly_entries=[HK_MONDAY_9AM, HK_SUNDAY_9AM],
    )
    with pytest.raises(ValidationError) as exc_info:
        _create(db_session, body)
    assert exc_info.value.field == "weekly_entries[1]"


def test_weekday_check_uses_the_hong_kong_day(
    db_session, sample_activity, sample_location
) -> None:
    body = _body(
        sample_activity,
        sample_location,
        weekly_entries=[HK_MONDAY_7AM],
        starts_on="2026-07-20",
        ends_on="2026-07-20",
    )
    schedule = _create(db_session, body)
    assert schedule.starts_on == date(2026, 7, 20)


def test_several_sessions_per_venue(
    db_session, sample_activity, sample_location
) -> None:
    _create(db_session, _body(sample_activity, sample_location))
    _create(
        db_session,
        _body(
            sample_activity,
            sample_location,
            starts_on="2026-07-27",
            ends_on="2026-08-01",
        ),
    )

    with pytest.raises(ValidationError):
        _create(db_session, _body(sample_activity, sample_location))


def test_one_undated_schedule_per_venue_and_languages(
    db_session, sample_activity, sample_location
) -> None:
    body = _body(sample_activity, sample_location)
    body.pop("starts_on")
    body.pop("ends_on")
    _create(db_session, body)
    _create(db_session, _body(sample_activity, sample_location))

    with pytest.raises(ValidationError):
        _create(db_session, dict(body))


def test_update_moves_a_session(db_session, sample_activity, sample_location) -> None:
    repo = ActivityScheduleRepository(db_session)
    first = _create(db_session, _body(sample_activity, sample_location))
    _create(
        db_session,
        _body(
            sample_activity,
            sample_location,
            starts_on="2026-07-27",
            ends_on="2026-08-01",
        ),
    )

    with pytest.raises(ValidationError):
        _update_schedule(
            repo, first, {"starts_on": "2026-07-27", "ends_on": "2026-08-01"}
        )

    _update_schedule(repo, first, {"starts_on": "2026-08-03", "ends_on": "2026-08-07"})
    assert first.ends_on == date(2026, 8, 7)

    _update_schedule(repo, first, {"starts_on": None, "ends_on": None})
    assert first.starts_on is None


def test_update_checks_new_entries_against_kept_dates(
    db_session, sample_activity, sample_location
) -> None:
    repo = ActivityScheduleRepository(db_session)
    schedule = _create(
        db_session,
        _body(
            sample_activity,
            sample_location,
            starts_on="2026-07-20",
            ends_on="2026-07-20",
        ),
    )

    with pytest.raises(ValidationError):
        _update_schedule(repo, schedule, {"weekly_entries": [HK_SUNDAY_9AM]})


def _camp_rows(start: str, end: str) -> dict:
    return {
        "location_name": "Studio",
        "timezone": "Asia/Hong_Kong",
        "languages": ["en"],
        "starts_on": start,
        "ends_on": end,
        "weekly_entries": [
            {"day_of_week": 1, "start_time": "09:00", "end_time": "12:00"},
            {"day_of_week": 2, "start_time": "09:00", "end_time": "12:00"},
        ],
    }


def test_import_keeps_one_schedule_per_session(
    db_session, sample_activity, sample_location
) -> None:
    warnings: list[str] = []
    first, status = upsert_schedule(
        db_session,
        sample_activity,
        sample_location,
        _camp_rows("2026-07-20", "2026-07-24"),
        warnings,
    )
    assert status == "created"
    second, status = upsert_schedule(
        db_session,
        sample_activity,
        sample_location,
        _camp_rows("2026-07-27", "2026-07-31"),
        warnings,
    )
    assert status == "created"
    assert first.id != second.id

    again, status = upsert_schedule(
        db_session,
        sample_activity,
        sample_location,
        _camp_rows("2026-07-20", "2026-07-24"),
        warnings,
    )
    assert status == "unchanged"
    assert again.id == first.id

    moved, status = upsert_schedule(
        db_session,
        sample_activity,
        sample_location,
        _camp_rows("2026-07-20", "2026-07-25"),
        warnings,
    )
    assert status == "updated"
    assert moved.id == first.id
    assert moved.ends_on == date(2026, 7, 25)


def test_export_includes_session_dates(
    db_session, sample_activity, sample_location
) -> None:
    schedule = _create(db_session, _body(sample_activity, sample_location))
    exported = serialize_export_schedule(
        schedule,
        {str(sample_location.id): "Studio"},
        ZoneInfo("Asia/Hong_Kong"),
        [],
    )
    assert exported["starts_on"] == "2026-07-20"
    assert exported["ends_on"] == "2026-07-25"


def test_version_payload_and_shape_carry_dates(
    db_session, sample_activity, sample_location
) -> None:
    schedule = _create(db_session, _body(sample_activity, sample_location))
    payload = schedule_payload(schedule, sample_location)
    assert payload["starts_on"] == "2026-07-20"
    shape = build_shape("schedule", payload)
    assert shape["starts_on"] == "2026-07-20"
    assert shape["ends_on"] == "2026-07-25"
    assert build_shape("schedule", {"starts_on": date(2026, 7, 20)})[
        "starts_on"
    ] == ("2026-07-20")


def test_org_merge_keeps_each_dated_session(
    db_session, sample_geographic_area, sample_activity_category
) -> None:
    survivor = Organization(name="Harbour Camps", manager_id="m", description="d")
    source = Organization(name="Harbour Camps Limited", manager_id="m", description="d")
    db_session.add_all([survivor, source])
    db_session.flush()
    venue = Location(
        org_id=survivor.id, area_id=sample_geographic_area.id, address="1 Pier Road"
    )
    db_session.add(venue)
    db_session.flush()

    def camp(org: Organization, *starts: date) -> Activity:
        activity = Activity(
            org_id=org.id,
            category_id=sample_activity_category.id,
            name="Harbour Camp",
            description="Camp",
            kind="camp",
            age_range=Range(5, 10, bounds="[]"),
        )
        db_session.add(activity)
        db_session.flush()
        for start in starts:
            schedule = ActivitySchedule(
                activity_id=activity.id,
                location_id=venue.id,
                schedule_type=ScheduleType.WEEKLY,
                languages=["en"],
                starts_on=start,
                ends_on=start,
            )
            schedule.entries = [
                ActivityScheduleEntry(
                    day_of_week_utc=1, start_minutes_utc=60, end_minutes_utc=240
                )
            ]
            db_session.add(schedule)
        db_session.flush()
        return activity

    kept = camp(survivor, date(2026, 7, 20))
    camp(source, date(2026, 7, 20), date(2026, 8, 3))

    merge_organizations(db_session, survivor.id, [source.id])

    starts = sorted(
        db_session.scalars(
            select(ActivitySchedule.starts_on).where(
                ActivitySchedule.activity_id == kept.id
            )
        )
    )
    assert starts == [date(2026, 7, 20), date(2026, 8, 3)]
