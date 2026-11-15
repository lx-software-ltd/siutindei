"""Review rules by listing kind, and the area readiness gate."""

from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from app.api import admin_org_review
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
from app.exceptions import ValidationError
from app.services.area_readiness import (
    READY_COMPLETE_SHARE,
    READY_VERIFIED_SHARE,
    area_readiness,
)
from app.services.org_review import load_snapshots, summarize_snapshots
from app.services.org_review_kinds import is_catch_all_age
from app.services.org_review_sql import (
    has_blocker_clause,
    issue_clause,
    summarize_catalog,
)
from psycopg.types.range import Range
from sqlalchemy import select

KIND_CODES = (
    "missing_pricing",
    "missing_schedule",
    "catch_all_age",
    "hours_as_class_times",
    "class_price_outlier",
    "verification_stale",
    "camp_without_dates",
)

_TODAY = datetime.now(UTC).date()
_ENDED = (_TODAY - timedelta(days=30), _TODAY - timedelta(days=26))
_UPCOMING = (_TODAY + timedelta(days=30), _TODAY + timedelta(days=36))


def _area(session, level: str = "neighbourhood", parent=None) -> GeographicArea:
    area = GeographicArea(
        name=f"Area {uuid4().hex[:8]}",
        level=level,
        parent_id=parent.id if parent else None,
        active=True,
    )
    session.add(area)
    session.flush()
    return area


def _category(session) -> ActivityCategory:
    category = ActivityCategory(name=f"Kind test {uuid4().hex[:8]}", display_order=0)
    session.add(category)
    session.flush()
    return category


def _org(session, area: GeographicArea, **overrides) -> tuple[Organization, Location]:
    organization = Organization(
        **{
            "name": f"Kind Org {uuid4().hex[:8]}",
            "manager_id": "00000000-0000-0000-0000-000000000061",
            "description": "Described",
            "review_status": "pending_review",
            **overrides,
        }
    )
    session.add(organization)
    session.flush()
    location = Location(
        org_id=organization.id,
        area_id=area.id,
        address="1 Example Road",
        lat=Decimal("22.218000"),
        lng=Decimal("114.212000"),
    )
    session.add(location)
    session.flush()
    return organization, location


def _activity(
    session,
    organization: Organization,
    location: Location,
    category: ActivityCategory,
    kind: str = "class",
    ages: tuple[int, int] = (3, 6),
    price: tuple[PricingType, str] | None = (PricingType.PER_CLASS, "180"),
    entries: list[tuple[int, int, int]] | None = None,
    dates: tuple[date, date] | None = None,
) -> Activity:
    activity = Activity(
        org_id=organization.id,
        category_id=category.id,
        name=f"{kind.title()} {uuid4().hex[:6]}",
        description="Described",
        kind=kind,
        age_range=Range(ages[0], ages[1], bounds="[]"),
    )
    session.add(activity)
    session.flush()
    session.add(ActivityLocation(activity_id=activity.id, location_id=location.id))
    if price is not None:
        session.add(
            ActivityPricing(
                activity_id=activity.id,
                location_id=location.id,
                pricing_type=price[0],
                amount=Decimal(price[1]),
                currency="HKD",
            )
        )
    if entries is None:
        entries = [(1, 600, 660)]
    if entries:
        session.add(
            ActivitySchedule(
                activity_id=activity.id,
                location_id=location.id,
                schedule_type=ScheduleType.WEEKLY,
                languages=["en"],
                starts_on=dates[0] if dates else None,
                ends_on=dates[1] if dates else None,
                entries=[
                    ActivityScheduleEntry(
                        day_of_week_utc=day,
                        start_minutes_utc=start,
                        end_minutes_utc=end,
                    )
                    for day, start, end in entries
                ],
            )
        )
    session.flush()
    return activity


def _issues(session, organization: Organization) -> dict[tuple[str, str], str]:
    """Issue code and entity id to severity, from the Python rules."""
    [snapshot] = load_snapshots(session, [organization])
    return {(issue.code, issue.entity_id): issue.severity for issue in snapshot.issues}


def _assert_sql_matches_python(session, organizations: list[Organization]) -> None:
    ids = [organization.id for organization in organizations]
    snapshots = load_snapshots(session, organizations)
    for code in KIND_CODES:
        sql_ids = set(
            session.scalars(
                select(Organization.id).where(
                    Organization.id.in_(ids), issue_clause(code)
                )
            ).all()
        )
        python_ids = {
            snapshot.organization.id
            for snapshot in snapshots
            if any(issue.code == code for issue in snapshot.issues)
        }
        assert sql_ids == python_ids, code
    sql_blocked = set(
        session.scalars(
            select(Organization.id).where(
                Organization.id.in_(ids), has_blocker_clause()
            )
        ).all()
    )
    assert sql_blocked == {
        snapshot.organization.id for snapshot in snapshots if snapshot.blocker_count
    }
    everyone = list(session.scalars(select(Organization)).all())
    assert summarize_catalog(session) == summarize_snapshots(
        load_snapshots(session, everyone)
    )


def test_classes_and_camps_need_a_price_and_a_schedule(db_session) -> None:
    area, category = _area(db_session), _category(db_session)
    organization, location = _org(db_session, area)
    bare_class = _activity(
        db_session, organization, location, category, price=None, entries=[]
    )
    bare_camp = _activity(
        db_session,
        organization,
        location,
        category,
        kind="camp",
        price=None,
        entries=[],
    )

    issues = _issues(db_session, organization)
    for activity in (bare_class, bare_camp):
        assert issues[("missing_pricing", str(activity.id))] == "blocker"
        assert issues[("missing_schedule", str(activity.id))] == "blocker"
    _assert_sql_matches_python(db_session, [organization])


def test_places_need_neither_and_preschools_only_warn_on_price(db_session) -> None:
    area, category = _area(db_session), _category(db_session)
    places, location = _org(db_session, area)
    for kind in ("place", "eat"):
        _activity(
            db_session, places, location, category, kind=kind, price=None, entries=[]
        )
    preschools, nursery_location = _org(db_session, area)
    nursery = _activity(
        db_session,
        preschools,
        nursery_location,
        category,
        kind="preschool",
        price=None,
        entries=[],
    )

    place_codes = {code for code, _entity in _issues(db_session, places)}
    assert "missing_pricing" not in place_codes
    assert "missing_schedule" not in place_codes
    nursery_issues = _issues(db_session, preschools)
    assert nursery_issues[("missing_pricing", str(nursery.id))] == "warning"
    assert ("missing_schedule", str(nursery.id)) not in nursery_issues
    assert "blocker" not in nursery_issues.values()
    _assert_sql_matches_python(db_session, [places, preschools])


def test_catch_all_age_excludes_the_import_default() -> None:
    assert is_catch_all_age(0, 99)
    assert is_catch_all_age(0, 25)
    assert not is_catch_all_age(0, 18)
    assert not is_catch_all_age(1, 99)
    assert not is_catch_all_age(5, 12)


def test_catch_all_ages_warn_for_classes_and_camps_only(db_session) -> None:
    area, category = _area(db_session), _category(db_session)
    organization, location = _org(db_session, area)
    import_default = _activity(
        db_session, organization, location, category, ages=(0, 18)
    )
    all_ages_place = _activity(
        db_session, organization, location, category, kind="place", ages=(0, 18)
    )
    narrow = _activity(db_session, organization, location, category, ages=(5, 12))

    issues = _issues(db_session, organization)
    assert ("catch_all_age", str(import_default.id)) not in issues
    assert issues[("default_age_range", str(import_default.id))] == "warning"
    assert ("default_age_range", str(all_ages_place.id)) not in issues
    assert ("catch_all_age", str(all_ages_place.id)) not in issues
    assert ("default_age_range", str(narrow.id)) not in issues
    _assert_sql_matches_python(db_session, [organization])


def test_long_hours_every_day_look_like_opening_hours(db_session) -> None:
    area, category = _area(db_session), _category(db_session)
    organization, location = _org(db_session, area)
    long_days = [(day, 60, 540) for day in range(6)]
    overnight_days = [(day, 1200, 120) for day in range(6)]
    hours = _activity(db_session, organization, location, category, entries=long_days)
    overnight = _activity(
        db_session, organization, location, category, entries=overnight_days
    )
    five_days = _activity(
        db_session, organization, location, category, entries=long_days[:5]
    )
    short = _activity(
        db_session,
        organization,
        location,
        category,
        entries=[(day, 60, 419) for day in range(7)],
    )
    place = _activity(
        db_session, organization, location, category, kind="place", entries=long_days
    )

    issues = _issues(db_session, organization)
    assert issues[("hours_as_class_times", str(hours.id))] == "warning"
    assert issues[("hours_as_class_times", str(overnight.id))] == "warning"
    for quiet in (five_days, short, place):
        assert ("hours_as_class_times", str(quiet.id)) not in issues
    _assert_sql_matches_python(db_session, [organization])


def test_class_price_above_the_threshold_is_flagged(db_session) -> None:
    area, category = _area(db_session), _category(db_session)
    organization, location = _org(db_session, area)
    term_fee = _activity(
        db_session,
        organization,
        location,
        category,
        price=(PricingType.PER_CLASS, "2400"),
    )
    hourly = _activity(
        db_session,
        organization,
        location,
        category,
        price=(PricingType.PER_HOUR, "1500.01"),
    )
    at_limit = _activity(
        db_session,
        organization,
        location,
        category,
        price=(PricingType.PER_CLASS, "1500"),
    )
    monthly = _activity(
        db_session,
        organization,
        location,
        category,
        price=(PricingType.PER_MONTH, "4000"),
    )

    issues = _issues(db_session, organization)
    assert issues[("class_price_outlier", str(term_fee.id))] == "warning"
    assert issues[("class_price_outlier", str(hourly.id))] == "warning"
    assert ("class_price_outlier", str(at_limit.id)) not in issues
    assert ("class_price_outlier", str(monthly.id)) not in issues
    _assert_sql_matches_python(db_session, [organization])


def test_old_or_undated_parent_checks_are_flagged_for_the_owner(db_session) -> None:
    area, category = _area(db_session), _category(db_session)
    now = datetime.now(UTC)
    old, old_location = _org(
        db_session,
        area,
        parent_verified=True,
        parent_verified_at=now - timedelta(days=400),
    )
    undated, undated_location = _org(db_session, area, parent_verified=True)
    fresh, fresh_location = _org(
        db_session,
        area,
        parent_verified=True,
        parent_verified_at=now - timedelta(days=30),
    )
    unverified, unverified_location = _org(db_session, area)
    for organization, location in (
        (old, old_location),
        (undated, undated_location),
        (fresh, fresh_location),
        (unverified, unverified_location),
    ):
        _activity(db_session, organization, location, category)

    assert _issues(db_session, old)[("verification_stale", str(old.id))] == "warning"
    assert ("verification_stale", str(undated.id)) in _issues(db_session, undated)
    assert ("verification_stale", str(fresh.id)) not in _issues(db_session, fresh)
    assert ("verification_stale", str(unverified.id)) not in _issues(
        db_session, unverified
    )
    assert old.parent_verified
    _assert_sql_matches_python(db_session, [old, undated, fresh, unverified])


def test_camps_without_upcoming_dates_are_flagged(db_session) -> None:
    area, category = _area(db_session), _category(db_session)
    organization, location = _org(db_session, area)
    undated = _activity(db_session, organization, location, category, kind="camp")
    ended = _activity(
        db_session, organization, location, category, kind="camp", dates=_ENDED
    )
    upcoming = _activity(
        db_session, organization, location, category, kind="camp", dates=_UPCOMING
    )
    unscheduled = _activity(
        db_session, organization, location, category, kind="camp", entries=[]
    )
    weekly_class = _activity(db_session, organization, location, category)

    issues = _issues(db_session, organization)
    assert issues[("camp_without_dates", str(undated.id))] == "warning"
    assert issues[("camp_without_dates", str(ended.id))] == "warning"
    for quiet in (upcoming, unscheduled, weekly_class):
        assert ("camp_without_dates", str(quiet.id)) not in issues
    assert issues[("missing_schedule", str(unscheduled.id))] == "blocker"
    _assert_sql_matches_python(db_session, [organization])


def test_a_camp_whose_sessions_ended_is_not_complete(db_session) -> None:
    area, category = _area(db_session), _category(db_session)
    organization, location = _org(db_session, area)
    _activity(db_session, organization, location, category, kind="camp", dates=_ENDED)
    _activity(db_session, organization, location, category, kind="camp")
    _activity(
        db_session, organization, location, category, kind="camp", dates=_UPCOMING
    )

    readiness = area_readiness(db_session, area.id)
    assert readiness["classes_and_camps"] == 3
    assert readiness["complete_classes_and_camps"] == 1


def _ready_area(db_session):
    district = _area(db_session, level="district")
    neighbourhood = _area(db_session, parent=district)
    elsewhere = _area(db_session)
    category = _category(db_session)
    verified, verified_location = _org(
        db_session,
        neighbourhood,
        parent_verified=True,
        parent_verified_at=datetime.now(UTC),
    )
    plain, plain_location = _org(db_session, neighbourhood)
    for _ in range(3):
        _activity(db_session, verified, verified_location, category)
    camp = _activity(
        db_session, plain, plain_location, category, kind="camp", dates=_UPCOMING
    )
    _activity(db_session, plain, plain_location, category, ages=(0, 18))
    _activity(db_session, plain, plain_location, category, kind="place", price=None)
    rejected, rejected_location = _org(
        db_session,
        neighbourhood,
        review_status="rejected",
        review_reason="not_relevant",
    )
    _activity(db_session, rejected, rejected_location, category, price=None)
    outside, outside_location = _org(db_session, elsewhere)
    _activity(db_session, outside, outside_location, category, price=None)
    return district, neighbourhood, camp


def test_area_readiness_counts_listings_complete_classes_and_checks(
    db_session,
) -> None:
    district, neighbourhood, camp = _ready_area(db_session)

    readiness = area_readiness(db_session, neighbourhood.id)
    assert readiness == area_readiness(db_session, district.id) | {
        "area_id": str(neighbourhood.id)
    }
    assert readiness["listings_by_kind"] == {
        "class": 4,
        "camp": 1,
        "place": 1,
        "preschool": 0,
        "eat": 0,
    }
    assert readiness["classes_and_camps"] == 5
    assert readiness["complete_classes_and_camps"] == 4
    assert readiness["organisers"] == 2
    assert readiness["verified_organisers"] == 1
    assert readiness["complete_share"] == pytest.approx(0.8)
    assert readiness["verified_share"] == pytest.approx(0.5)
    assert readiness["thresholds"] == {
        "complete_share": READY_COMPLETE_SHARE,
        "verified_share": READY_VERIFIED_SHARE,
    }
    assert readiness["ready"] is True

    for pricing in db_session.scalars(
        select(ActivityPricing).where(ActivityPricing.activity_id == camp.id)
    ):
        db_session.delete(pricing)
    db_session.flush()
    not_ready = area_readiness(db_session, neighbourhood.id)
    assert not_ready["complete_classes_and_camps"] == 3
    assert not_ready["ready"] is False


def test_an_empty_area_is_not_ready(db_session) -> None:
    empty = _area(db_session)

    readiness = area_readiness(db_session, empty.id)
    assert readiness["classes_and_camps"] == 0
    assert readiness["complete_share"] is None
    assert readiness["verified_share"] is None
    assert readiness["ready"] is False


def _summary(db_session, monkeypatch, area_id: str | None) -> dict:
    monkeypatch.setattr(admin_org_review, "get_engine", lambda: None)
    monkeypatch.setattr(
        admin_org_review, "Session", lambda _engine: nullcontext(db_session)
    )
    event = {"queryStringParameters": {"area_id": area_id} if area_id else None}
    return admin_org_review._handle_summary(event)


def test_summary_adds_readiness_only_for_an_area(db_session, monkeypatch) -> None:
    _district, neighbourhood, _camp = _ready_area(db_session)

    plain = json.loads(_summary(db_session, monkeypatch, None)["body"])
    assert "readiness" not in plain
    with_area = json.loads(
        _summary(db_session, monkeypatch, str(neighbourhood.id))["body"]
    )
    assert with_area["readiness"]["ready"] is True
    assert {
        key: value for key, value in with_area.items() if key != "readiness"
    } == plain

    with pytest.raises(ValidationError):
        _summary(db_session, monkeypatch, str(uuid4()))
    with pytest.raises(ValidationError):
        _summary(db_session, monkeypatch, "not-a-uuid")
