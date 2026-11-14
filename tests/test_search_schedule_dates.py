"""Search drops ended sessions, filters by date, and returns session dates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.api.search import fetch_search_response, parse_filters
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.enums import PricingType, ScheduleType
from app.db.queries import ActivitySearchFilters
from app.exceptions import ValidationError
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.orm import Session

_MANAGER = "00000000-0000-0000-0000-000000000001"
TODAY = date(2026, 11, 13)


def _seed(engine) -> dict[str, str]:
    token = uuid4().hex[:8]
    with Session(engine) as session:
        area = GeographicArea(name=f"Area {token}", level="neighbourhood", active=True)
        category = ActivityCategory(name=f"Category {token}", display_order=0)
        org = Organization(
            name=f"Dates Club {token}",
            manager_id=_MANAGER,
            description="Dates",
            review_status="approved",
        )
        session.add_all([area, category, org])
        session.flush()
        venue = Location(
            org_id=org.id,
            area_id=area.id,
            address=f"Venue {token}",
            lat=Decimal("22.2"),
            lng=Decimal("114.2"),
        )
        session.add(venue)
        session.flush()

        def listing(label: str, kind: str, *sessions: tuple[date, date] | None):
            activity = Activity(
                org_id=org.id,
                category_id=category.id,
                name=f"{label} {token}",
                description=label,
                kind=kind,
                age_range=Range(5, 10, bounds="[]"),
            )
            session.add(activity)
            session.flush()
            session.add(
                ActivityPricing(
                    activity_id=activity.id,
                    location_id=venue.id,
                    pricing_type=PricingType.PER_SESSIONS,
                    amount=Decimal(2000),
                    sessions_count=4,
                )
            )
            for dates in sessions:
                schedule = ActivitySchedule(
                    activity_id=activity.id,
                    location_id=venue.id,
                    schedule_type=ScheduleType.WEEKLY,
                    languages=["en"],
                    starts_on=None if dates is None else dates[0],
                    ends_on=None if dates is None else dates[1],
                )
                session.add(schedule)
                session.flush()
                session.add(
                    ActivityScheduleEntry(
                        schedule_id=schedule.id,
                        day_of_week_utc=1,
                        start_minutes_utc=60,
                        end_minutes_utc=240,
                    )
                )
            return str(activity.id)

        ids = {
            "weekly": listing("Weekly class", "class", None),
            "ended": listing(
                "Ended camp", "camp", (date(2026, 7, 20), date(2026, 7, 24))
            ),
            "winter": listing(
                "Winter camp", "camp", (date(2026, 12, 21), date(2026, 12, 24))
            ),
            "both": listing(
                "Two-session camp",
                "camp",
                (date(2026, 7, 20), date(2026, 7, 24)),
                (date(2026, 12, 21), date(2026, 12, 24)),
            ),
        }
        session.commit()
        return {
            **ids,
            "org_id": str(org.id),
            "area_id": str(area.id),
            "category_id": str(category.id),
        }


def _delete(engine, seeded: dict[str, str]) -> None:
    with Session(engine) as session:
        for model, key in (
            (Organization, "org_id"),
            (GeographicArea, "area_id"),
            (ActivityCategory, "category_id"),
        ):
            row = session.get(model, seeded[key])
            if row is not None:
                session.delete(row)
        session.commit()


@pytest.fixture
def seeded(monkeypatch, test_engine):
    monkeypatch.setattr("app.api.search.get_engine", lambda: test_engine)
    data = _seed(test_engine)
    yield data
    _delete(test_engine, data)


def _search(seeded, **kwargs):
    filters = ActivitySearchFilters(
        org_ids=(UUID(seeded["org_id"]),), limit=20, today=TODAY, **kwargs
    )
    return fetch_search_response(filters)


def _ids(response) -> set[str]:
    return {item.activity.id for item in response.items}


def test_an_ended_session_is_absent(seeded) -> None:
    response = _search(seeded)
    assert _ids(response) == {seeded["weekly"], seeded["winter"], seeded["both"]}
    by_id = {item.activity.id: item for item in response.items}
    assert by_id[seeded["both"]].schedule.starts_on == "2026-12-21"
    assert by_id[seeded["both"]].schedule.ends_on == "2026-12-24"
    assert by_id[seeded["weekly"]].schedule.starts_on is None


def test_a_camp_whose_sessions_ended_is_incomplete(seeded) -> None:
    response = _search(seeded, include_incomplete=True)
    by_id = {item.activity.id: item for item in response.items}
    assert set(by_id) == {
        seeded["weekly"],
        seeded["ended"],
        seeded["winter"],
        seeded["both"],
    }
    assert by_id[seeded["ended"]].schedule is None


def test_the_session_counts_until_its_last_day(seeded) -> None:
    filters = ActivitySearchFilters(
        org_ids=(UUID(seeded["org_id"]),), limit=20, today=date(2026, 7, 24)
    )
    assert seeded["ended"] in _ids(fetch_search_response(filters))


def test_a_date_window_keeps_overlapping_and_undated_schedules(seeded) -> None:
    christmas = _search(
        seeded, date_from=date(2026, 12, 22), date_to=date(2026, 12, 23)
    )
    assert _ids(christmas) == {seeded["weekly"], seeded["winter"], seeded["both"]}

    january = _search(seeded, date_from=date(2027, 1, 4), date_to=date(2027, 1, 8))
    assert _ids(january) == {seeded["weekly"]}

    before = _search(seeded, date_to=date(2026, 12, 20))
    assert _ids(before) == {seeded["weekly"]}


def test_a_date_window_drops_incomplete_rows_with_other_dates(seeded) -> None:
    response = _search(
        seeded,
        include_incomplete=True,
        date_from=date(2027, 1, 4),
        date_to=date(2027, 1, 8),
    )
    assert _ids(response) == {seeded["weekly"], seeded["ended"]}


def test_parse_filters_reads_the_date_window() -> None:
    filters = parse_filters(
        {
            "queryStringParameters": {
                "date_from": "2026-12-19",
                "date_to": "2026-12-20",
            }
        }
    )
    assert filters.date_from == date(2026, 12, 19)
    assert filters.date_to == date(2026, 12, 20)


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"date_from": "2026-12-21", "date_to": "2026-12-20"}, "date_from"),
        ({"date_from": "21/12/2026"}, "date_from"),
        ({"date_to": "soon"}, "date_to"),
    ],
)
def test_parse_filters_rejects_a_bad_window(params, field) -> None:
    with pytest.raises(ValidationError) as exc_info:
        parse_filters({"queryStringParameters": params})
    assert exc_info.value.field == field
