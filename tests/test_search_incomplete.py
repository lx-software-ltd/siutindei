"""Approved activities missing a price or schedule stay searchable."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID, uuid4

from app.api.search import fetch_search_response
from app.api.search_page import parse_cursor as _parse_cursor
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityLocation,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.enums import PricingType, ScheduleType
from app.db.queries import ActivitySearchFilters
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.orm import Session

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _patch_engine(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.search.get_engine", lambda: engine)


def _seed(engine) -> dict[str, str]:
    token = uuid4().hex[:8]
    with Session(engine) as session:
        area = GeographicArea(
            name=f"Area {token}",
            level="neighbourhood",
            active=True,
        )
        category = ActivityCategory(name=f"Category {token}", display_order=0)
        approved = Organization(
            name=f"Approved Club {token}",
            manager_id=_MANAGER,
            description="Approved",
            review_status="approved",
        )
        pending = Organization(
            name=f"Pending Club {token}",
            manager_id=_MANAGER,
            description="Pending",
            review_status="pending_review",
        )
        session.add_all([area, category, approved, pending])
        session.flush()

        def venue(org: Organization, label: str) -> Location:
            row = Location(
                org_id=org.id,
                area_id=area.id,
                address=f"{label} {token}",
                lat=Decimal("22.200000"),
                lng=Decimal("114.200000"),
            )
            session.add(row)
            session.flush()
            return row

        def activity(org: Organization, label: str) -> Activity:
            row = Activity(
                org_id=org.id,
                category_id=category.id,
                name=f"{label} {token}",
                description=label,
                age_range=Range(5, 12, bounds="[]"),
            )
            session.add(row)
            session.flush()
            return row

        def priced(act: Activity, loc: Location) -> None:
            session.add(
                ActivityPricing(
                    activity_id=act.id,
                    location_id=loc.id,
                    pricing_type=PricingType.PER_CLASS,
                    amount=Decimal("10.00"),
                )
            )

        def scheduled(act: Activity, loc: Location) -> None:
            schedule = ActivitySchedule(
                activity_id=act.id,
                location_id=loc.id,
                schedule_type=ScheduleType.WEEKLY,
                languages=["en"],
            )
            session.add(schedule)
            session.flush()
            session.add(
                ActivityScheduleEntry(
                    schedule_id=schedule.id,
                    day_of_week_utc=1,
                    start_minutes_utc=540,
                    end_minutes_utc=600,
                )
            )

        complete_location = venue(approved, "Complete venue")
        complete = activity(approved, "Complete class")
        priced(complete, complete_location)
        scheduled(complete, complete_location)

        priced_location = venue(approved, "Priced venue")
        priced_only = activity(approved, "Priced class")
        priced(priced_only, priced_location)

        scheduled_location = venue(approved, "Scheduled venue")
        scheduled_only = activity(approved, "Scheduled class")
        scheduled(scheduled_only, scheduled_location)

        linked_location = venue(approved, "Linked venue")
        linked = activity(approved, "Linked class")
        session.add(
            ActivityLocation(activity_id=linked.id, location_id=linked_location.id)
        )

        pending_location = venue(pending, "Pending venue")
        pending_activity = activity(pending, "Pending class")
        session.add(
            ActivityLocation(
                activity_id=pending_activity.id,
                location_id=pending_location.id,
            )
        )
        session.commit()
        return {
            "area_id": str(area.id),
            "category_id": str(category.id),
            "approved_id": str(approved.id),
            "pending_id": str(pending.id),
            "complete_id": str(complete.id),
            "priced_id": str(priced_only.id),
            "scheduled_id": str(scheduled_only.id),
            "linked_id": str(linked.id),
            "pending_activity_id": str(pending_activity.id),
        }


def _delete(engine, seeded: dict[str, str]) -> None:
    with Session(engine) as session:
        for key in ("approved_id", "pending_id"):
            row = session.get(Organization, seeded[key])
            if row is not None:
                session.delete(row)
        area = session.get(GeographicArea, seeded["area_id"])
        category = session.get(ActivityCategory, seeded["category_id"])
        if area is not None:
            session.delete(area)
        if category is not None:
            session.delete(category)
        session.commit()


def _ids(response) -> set[str]:
    return {item.activity.id for item in response.items}


def test_include_incomplete_returns_approved_activities_missing_price_or_schedule(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    seeded = _seed(test_engine)
    approved = (UUID(seeded["approved_id"]),)
    try:
        hidden = fetch_search_response(
            ActivitySearchFilters(org_ids=approved, limit=20)
        )
        assert _ids(hidden) == {seeded["complete_id"]}

        shown = fetch_search_response(
            ActivitySearchFilters(
                org_ids=approved,
                limit=20,
                include_incomplete=True,
            )
        )
        assert _ids(shown) == {
            seeded["complete_id"],
            seeded["priced_id"],
            seeded["scheduled_id"],
            seeded["linked_id"],
        }
        by_id = {item.activity.id: item for item in shown.items}
        assert by_id[seeded["priced_id"]].pricing is not None
        assert by_id[seeded["priced_id"]].schedule is None
        assert by_id[seeded["scheduled_id"]].pricing is None
        assert by_id[seeded["scheduled_id"]].schedule is not None
        assert by_id[seeded["linked_id"]].pricing is None
        assert by_id[seeded["linked_id"]].schedule is None
        assert by_id[seeded["complete_id"]].pricing is not None
        assert by_id[seeded["complete_id"]].schedule is not None

        pending = fetch_search_response(
            ActivitySearchFilters(
                org_ids=(UUID(seeded["pending_id"]),),
                limit=20,
                include_incomplete=True,
            )
        )
        assert pending.items == []

        priced = fetch_search_response(
            ActivitySearchFilters(
                org_ids=approved,
                limit=20,
                include_incomplete=True,
                price_min=Decimal(1),
            )
        )
        assert _ids(priced) == {seeded["complete_id"], seeded["priced_id"]}

        monday = fetch_search_response(
            ActivitySearchFilters(
                org_ids=approved,
                limit=20,
                include_incomplete=True,
                day_of_week_utc=1,
            )
        )
        assert _ids(monday) == {seeded["complete_id"], seeded["scheduled_id"]}
    finally:
        _delete(test_engine, seeded)


def test_incomplete_rows_follow_complete_rows_in_a_later_page(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    seeded = _seed(test_engine)
    approved = (UUID(seeded["approved_id"]),)
    try:
        first = fetch_search_response(
            ActivitySearchFilters(
                org_ids=approved,
                limit=1,
                include_incomplete=True,
            )
        )
        assert _ids(first) == {seeded["complete_id"]}
        assert first.next_cursor
        cursor = _parse_cursor(first.next_cursor)
        assert cursor is not None
        assert cursor.phase == "incomplete"
        second = fetch_search_response(
            ActivitySearchFilters(
                org_ids=approved,
                limit=10,
                include_incomplete=True,
                cursor=cursor,
            )
        )
        assert seeded["complete_id"] not in _ids(second)
        assert _ids(second) == {
            seeded["priced_id"],
            seeded["scheduled_id"],
            seeded["linked_id"],
        }
        assert second.next_cursor is None
    finally:
        _delete(test_engine, seeded)


def test_include_incomplete_rejects_a_non_boolean(monkeypatch) -> None:
    from app.api.search import parse_filters
    from app.exceptions import ValidationError

    event = {"queryStringParameters": {"include_incomplete": "maybe"}}
    try:
        parse_filters(event)
    except ValidationError as exc:
        assert exc.field == "include_incomplete"
        return
    raise AssertionError(json.dumps(event))
