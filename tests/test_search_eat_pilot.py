"""An eat listing is public only when a parent verified its organiser."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.api.search import fetch_search_response
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
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.orm import Session

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _seed(engine) -> dict[str, str]:
    token = uuid4().hex[:8]
    with Session(engine) as session:
        area = GeographicArea(name=f"Area {token}", level="neighbourhood", active=True)
        category = ActivityCategory(name=f"Category {token}", display_order=0)
        session.add_all([area, category])
        session.flush()

        def organiser(label: str, verified: bool) -> tuple[Organization, Location]:
            org = Organization(
                name=f"{label} {token}",
                manager_id=_MANAGER,
                description=label,
                review_status="approved",
                parent_verified=verified,
            )
            session.add(org)
            session.flush()
            venue = Location(
                org_id=org.id,
                area_id=area.id,
                address=f"{label} venue {token}",
                lat=Decimal("22.2"),
                lng=Decimal("114.2"),
            )
            session.add(venue)
            session.flush()
            return org, venue

        def listing(
            org: Organization, venue: Location, kind: str, *, complete: bool = True
        ) -> str:
            activity = Activity(
                org_id=org.id,
                category_id=category.id,
                name=f"{kind} at {org.name}" + ("" if complete else " (no hours)"),
                description=kind,
                kind=kind,
                age_range=Range(0, 12, bounds="[]"),
            )
            session.add(activity)
            session.flush()
            session.add(
                ActivityPricing(
                    activity_id=activity.id,
                    location_id=venue.id,
                    pricing_type=PricingType.FREE,
                    amount=Decimal(0),
                )
            )
            if complete:
                schedule = ActivitySchedule(
                    activity_id=activity.id,
                    location_id=venue.id,
                    schedule_type=ScheduleType.WEEKLY,
                    languages=["en"],
                )
                session.add(schedule)
                session.flush()
                session.add(
                    ActivityScheduleEntry(
                        schedule_id=schedule.id,
                        day_of_week_utc=1,
                        start_minutes_utc=60,
                        end_minutes_utc=600,
                    )
                )
            return str(activity.id)

        verified, verified_venue = organiser("Checked Cafe", True)
        unverified, unverified_venue = organiser("Unchecked Cafe", False)
        ids = {
            "verified_eat": listing(verified, verified_venue, "eat"),
            "verified_eat_no_hours": listing(
                verified, verified_venue, "eat", complete=False
            ),
            "unverified_eat": listing(unverified, unverified_venue, "eat"),
            "unverified_eat_no_hours": listing(
                unverified, unverified_venue, "eat", complete=False
            ),
            "unverified_class": listing(unverified, unverified_venue, "class"),
        }
        session.commit()
        return {
            **ids,
            "verified_org": str(verified.id),
            "unverified_org": str(unverified.id),
            "area_id": str(area.id),
            "category_id": str(category.id),
        }


def _delete(engine, seeded: dict[str, str]) -> None:
    with Session(engine) as session:
        for model, key in (
            (Organization, "verified_org"),
            (Organization, "unverified_org"),
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


def _ids(seeded, **kwargs) -> set[str]:
    filters = ActivitySearchFilters(
        org_ids=(UUID(seeded["verified_org"]), UUID(seeded["unverified_org"])),
        limit=20,
        **kwargs,
    )
    return {item.activity.id for item in fetch_search_response(filters).items}


def test_an_unverified_eat_listing_is_absent(seeded) -> None:
    assert _ids(seeded) == {seeded["verified_eat"], seeded["unverified_class"]}
    assert _ids(seeded, kinds=("eat",)) == {seeded["verified_eat"]}


def test_an_unverified_eat_listing_is_absent_from_incomplete_results(seeded) -> None:
    assert _ids(seeded, include_incomplete=True) == {
        seeded["verified_eat"],
        seeded["verified_eat_no_hours"],
        seeded["unverified_class"],
    }


def test_a_direct_lookup_does_not_open_an_unverified_eat_listing(seeded) -> None:
    lookup = _ids(
        seeded, activity_id=UUID(seeded["unverified_eat"]), include_incomplete=True
    )
    assert lookup == set()
