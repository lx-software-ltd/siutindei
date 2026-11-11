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


def test_area_filter_uses_the_venue_inside_the_area(monkeypatch, test_engine) -> None:
    """A venue outside the area must not hide the venue inside it."""

    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        outside = GeographicArea(
            name=f"Outside {token}", level="neighbourhood", active=True
        )
        inside = GeographicArea(
            name=f"Inside {token}", level="neighbourhood", active=True
        )
        category = ActivityCategory(name=f"Area category {token}", display_order=0)
        org = Organization(
            name=f"Area club {token}",
            manager_id=_MANAGER,
            description="Approved",
            review_status="approved",
        )
        session.add_all([outside, inside, category, org])
        session.flush()
        far = Location(
            org_id=org.id,
            area_id=outside.id,
            address=f"Far {token}",
            lat=Decimal("22.200000"),
            lng=Decimal("114.200000"),
        )
        near = Location(
            org_id=org.id,
            area_id=inside.id,
            address=f"Near {token}",
            lat=Decimal("22.210000"),
            lng=Decimal("114.210000"),
        )
        session.add_all([far, near])
        session.flush()
        row = Activity(
            org_id=org.id,
            category_id=category.id,
            name=f"Split area {token}",
            description="Two venues",
            age_range=Range(5, 12, bounds="[]"),
        )
        session.add(row)
        session.flush()
        schedule = ActivitySchedule(
            activity_id=row.id,
            location_id=far.id,
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
        session.add(ActivityLocation(activity_id=row.id, location_id=near.id))
        session.commit()
        org_id, inside_id, near_id, far_id = org.id, inside.id, near.id, far.id
        outside_id, category_id = outside.id, category.id
    try:
        shown = fetch_search_response(
            ActivitySearchFilters(
                org_ids=(org_id,),
                area_id=inside_id,
                limit=20,
                include_incomplete=True,
            )
        )
        assert len(shown.items) == 1
        assert shown.items[0].location.id == str(near_id)
        assert shown.items[0].location.id != str(far_id)
    finally:
        _delete(
            test_engine,
            {
                "approved_id": str(org_id),
                "pending_id": str(uuid4()),
                "area_id": str(inside_id),
                "category_id": str(category_id),
            },
        )
        with Session(test_engine) as session:
            extra = session.get(GeographicArea, outside_id)
            if extra is not None:
                session.delete(extra)
            session.commit()


def test_price_filter_uses_the_priced_venue(monkeypatch, test_engine) -> None:
    """A schedule venue without a price must not hide the priced venue."""

    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        area = GeographicArea(
            name=f"Price area {token}", level="neighbourhood", active=True
        )
        category = ActivityCategory(name=f"Price category {token}", display_order=0)
        org = Organization(
            name=f"Price club {token}",
            manager_id=_MANAGER,
            description="Approved",
            review_status="approved",
        )
        session.add_all([area, category, org])
        session.flush()
        scheduled_at = Location(
            org_id=org.id,
            area_id=area.id,
            address=f"Scheduled only {token}",
            lat=Decimal("22.200000"),
            lng=Decimal("114.200000"),
        )
        priced_at = Location(
            org_id=org.id,
            area_id=area.id,
            address=f"Priced only {token}",
            lat=Decimal("22.210000"),
            lng=Decimal("114.210000"),
        )
        session.add_all([scheduled_at, priced_at])
        session.flush()
        row = Activity(
            org_id=org.id,
            category_id=category.id,
            name=f"Split price {token}",
            description="Price elsewhere",
            age_range=Range(5, 12, bounds="[]"),
        )
        session.add(row)
        session.flush()
        schedule = ActivitySchedule(
            activity_id=row.id,
            location_id=scheduled_at.id,
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
        session.add(
            ActivityPricing(
                activity_id=row.id,
                location_id=priced_at.id,
                pricing_type=PricingType.PER_CLASS,
                amount=Decimal("10.00"),
            )
        )
        session.commit()
        org_id, area_id, category_id = org.id, area.id, category.id
        priced_id = priced_at.id
    try:
        shown = fetch_search_response(
            ActivitySearchFilters(
                org_ids=(org_id,),
                limit=20,
                include_incomplete=True,
                price_min=Decimal(1),
            )
        )
        assert len(shown.items) == 1
        assert shown.items[0].location.id == str(priced_id)
        assert shown.items[0].pricing is not None
    finally:
        _delete(
            test_engine,
            {
                "approved_id": str(org_id),
                "pending_id": str(uuid4()),
                "area_id": str(area_id),
                "category_id": str(category_id),
            },
        )


def test_a_complete_listing_is_not_also_an_incomplete_row(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        area = GeographicArea(
            name=f"Once area {token}", level="neighbourhood", active=True
        )
        category = ActivityCategory(name=f"Once category {token}", display_order=0)
        org = Organization(
            name=f"Once club {token}",
            manager_id=_MANAGER,
            description="Approved",
            review_status="approved",
        )
        session.add_all([area, category, org])
        session.flush()
        primary = Location(
            org_id=org.id,
            area_id=area.id,
            address=f"Primary {token}",
            lat=Decimal("22.200000"),
            lng=Decimal("114.200000"),
        )
        extra = Location(
            org_id=org.id,
            area_id=area.id,
            address=f"Extra {token}",
            lat=Decimal("22.210000"),
            lng=Decimal("114.210000"),
        )
        session.add_all([primary, extra])
        session.flush()
        row = Activity(
            org_id=org.id,
            category_id=category.id,
            name=f"Once class {token}",
            description="Complete plus a link",
            age_range=Range(5, 12, bounds="[]"),
        )
        session.add(row)
        session.flush()
        session.add(
            ActivityPricing(
                activity_id=row.id,
                location_id=primary.id,
                pricing_type=PricingType.PER_CLASS,
                amount=Decimal("10.00"),
            )
        )
        schedule = ActivitySchedule(
            activity_id=row.id,
            location_id=primary.id,
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
        session.add(ActivityLocation(activity_id=row.id, location_id=extra.id))
        session.commit()
        org_id, area_id, category_id, primary_id = (
            org.id,
            area.id,
            category.id,
            primary.id,
        )
    try:
        shown = fetch_search_response(
            ActivitySearchFilters(org_ids=(org_id,), limit=20, include_incomplete=True)
        )
        assert len(shown.items) == 1
        assert shown.items[0].location.id == str(primary_id)
        assert shown.items[0].pricing is not None
        assert shown.items[0].schedule is not None
    finally:
        _delete(
            test_engine,
            {
                "approved_id": str(org_id),
                "pending_id": str(uuid4()),
                "area_id": str(area_id),
                "category_id": str(category_id),
            },
        )


def test_a_closed_venue_is_not_the_chosen_venue(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        area = GeographicArea(
            name=f"Closed area {token}", level="neighbourhood", active=True
        )
        category = ActivityCategory(name=f"Closed category {token}", display_order=0)
        org = Organization(
            name=f"Closed club {token}",
            manager_id=_MANAGER,
            description="Approved",
            review_status="approved",
        )
        session.add_all([area, category, org])
        session.flush()
        closed = Location(
            org_id=org.id,
            area_id=area.id,
            address=f"Closed {token}",
            lat=Decimal("22.200000"),
            lng=Decimal("114.200000"),
            status="permanently_closed",
        )
        open_venue = Location(
            org_id=org.id,
            area_id=area.id,
            address=f"Open {token}",
            lat=Decimal("22.210000"),
            lng=Decimal("114.210000"),
        )
        only_closed = Location(
            org_id=org.id,
            area_id=area.id,
            address=f"Only closed {token}",
            lat=Decimal("22.220000"),
            lng=Decimal("114.220000"),
            status="permanently_closed",
        )
        session.add_all([closed, open_venue, only_closed])
        session.flush()

        def make(name: str) -> Activity:
            row = Activity(
                org_id=org.id,
                category_id=category.id,
                name=f"{name} {token}",
                description=name,
                age_range=Range(5, 12, bounds="[]"),
            )
            session.add(row)
            session.flush()
            return row

        visible = make("Open link")
        schedule = ActivitySchedule(
            activity_id=visible.id,
            location_id=closed.id,
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
        session.add(ActivityLocation(activity_id=visible.id, location_id=open_venue.id))
        hidden = make("Closed only")
        session.add(ActivityLocation(activity_id=hidden.id, location_id=only_closed.id))
        session.commit()
        org_id, area_id, category_id = org.id, area.id, category.id
        visible_id, open_id = visible.id, open_venue.id
    try:
        shown = fetch_search_response(
            ActivitySearchFilters(org_ids=(org_id,), limit=20, include_incomplete=True)
        )
        assert [item.activity.id for item in shown.items] == [str(visible_id)]
        assert shown.items[0].location.id == str(open_id)
    finally:
        _delete(
            test_engine,
            {
                "approved_id": str(org_id),
                "pending_id": str(uuid4()),
                "area_id": str(area_id),
                "category_id": str(category_id),
            },
        )


def test_incomplete_rows_stay_approved_when_the_review_gate_is_off(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.delenv("ORG_REVIEW_GATE_ENABLED", raising=False)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        area = GeographicArea(
            name=f"Gate area {token}", level="neighbourhood", active=True
        )
        category = ActivityCategory(name=f"Gate category {token}", display_order=0)
        approved = Organization(
            name=f"Gate approved {token}",
            manager_id=_MANAGER,
            description="Approved",
            review_status="approved",
        )
        pending = Organization(
            name=f"Gate pending {token}",
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

        def make(org: Organization, label: str) -> Activity:
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

        approved_venue = venue(approved, "Approved")
        approved_row = make(approved, "Approved link")
        session.add(
            ActivityLocation(activity_id=approved_row.id, location_id=approved_venue.id)
        )
        pending_link_venue = venue(pending, "Pending link")
        pending_link = make(pending, "Pending link")
        session.add(
            ActivityLocation(
                activity_id=pending_link.id, location_id=pending_link_venue.id
            )
        )
        pending_complete_venue = venue(pending, "Pending complete")
        pending_complete = make(pending, "Pending complete")
        session.add(
            ActivityPricing(
                activity_id=pending_complete.id,
                location_id=pending_complete_venue.id,
                pricing_type=PricingType.PER_CLASS,
                amount=Decimal("10.00"),
            )
        )
        schedule = ActivitySchedule(
            activity_id=pending_complete.id,
            location_id=pending_complete_venue.id,
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
        session.commit()
        approved_org, pending_org = approved.id, pending.id
        area_id, category_id = area.id, category.id
        approved_activity, pending_complete_id = approved_row.id, pending_complete.id
    try:
        shown = fetch_search_response(
            ActivitySearchFilters(
                org_ids=(approved_org, pending_org),
                limit=20,
                include_incomplete=True,
            )
        )
        assert _ids(shown) == {str(approved_activity), str(pending_complete_id)}
    finally:
        _delete(
            test_engine,
            {
                "approved_id": str(approved_org),
                "pending_id": str(pending_org),
                "area_id": str(area_id),
                "category_id": str(category_id),
            },
        )


def test_incomplete_rows_are_ordered_by_name(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    alpha_id = UUID("00000000-0000-4000-8000-000000000002")
    zulu_id = UUID("00000000-0000-4000-8000-000000000001")
    with Session(test_engine) as session:
        area = GeographicArea(
            name=f"Name area {token}", level="neighbourhood", active=True
        )
        category = ActivityCategory(name=f"Name category {token}", display_order=0)
        org = Organization(
            name=f"Name club {token}",
            manager_id=_MANAGER,
            description="Approved",
            review_status="approved",
        )
        session.add_all([area, category, org])
        session.flush()

        def linked(activity_id: UUID, label: str) -> None:
            place = Location(
                org_id=org.id,
                area_id=area.id,
                address=f"{label} {token}",
                lat=Decimal("22.200000"),
                lng=Decimal("114.200000"),
            )
            session.add(place)
            session.flush()
            row = Activity(
                id=activity_id,
                org_id=org.id,
                category_id=category.id,
                name=f"{label} {token}",
                description=label,
                age_range=Range(5, 12, bounds="[]"),
            )
            session.add(row)
            session.flush()
            session.add(ActivityLocation(activity_id=row.id, location_id=place.id))

        linked(alpha_id, "Alpha")
        linked(zulu_id, "Zulu")
        session.commit()
        org_id, area_id, category_id = org.id, area.id, category.id
    try:
        first = fetch_search_response(
            ActivitySearchFilters(org_ids=(org_id,), limit=1, include_incomplete=True)
        )
        assert [item.activity.id for item in first.items] == [str(alpha_id)]
        assert first.next_cursor
        cursor = _parse_cursor(first.next_cursor)
        second = fetch_search_response(
            ActivitySearchFilters(
                org_ids=(org_id,),
                limit=10,
                include_incomplete=True,
                cursor=cursor,
            )
        )
        assert [item.activity.id for item in second.items] == [str(zulu_id)]
    finally:
        _delete(
            test_engine,
            {
                "approved_id": str(org_id),
                "pending_id": str(uuid4()),
                "area_id": str(area_id),
                "category_id": str(category_id),
            },
        )


def test_incomplete_cursor_is_ignored_without_the_flag(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    seeded = _seed(test_engine)
    approved = (UUID(seeded["approved_id"]),)
    try:
        first = fetch_search_response(
            ActivitySearchFilters(org_ids=approved, limit=1, include_incomplete=True)
        )
        cursor = _parse_cursor(first.next_cursor)
        assert cursor is not None
        assert cursor.phase == "incomplete"
        hidden = fetch_search_response(
            ActivitySearchFilters(org_ids=approved, limit=10, cursor=cursor)
        )
        assert hidden.items == []
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
