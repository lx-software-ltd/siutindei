"""A price can be a range. amount stays the lower bound."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.api.admin_resource_pricing import (
    _create_pricing,
    _serialize_pricing,
    _update_pricing,
)
from app.api.schemas import dump_search_response
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
    PricingType,
    ScheduleType,
)
from app.db.queries import ActivitySearchFilters
from app.db.repositories import ActivityPricingRepository
from app.db.search_conditions import amounts_overlap
from app.exceptions import ValidationError
from app.services.catalog_version_shape import pricing_shape
from app.services.enrichment.row_blockers import pricing_fields, row_blockers
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_MANAGER = "00000000-0000-0000-0000-000000000001"


def test_amounts_overlap_keeps_a_single_price_and_spans_a_range() -> None:
    assert amounts_overlap(Decimal(200), None, Decimal(150), Decimal(250))
    assert not amounts_overlap(Decimal(200), None, Decimal(250), None)
    assert amounts_overlap(Decimal(200), Decimal(400), Decimal(350), None)
    assert amounts_overlap(Decimal(200), Decimal(400), Decimal(250), Decimal(300))
    assert not amounts_overlap(Decimal(200), Decimal(400), None, Decimal(150))
    assert not amounts_overlap(Decimal(100), None, Decimal(250), Decimal(300))


def test_create_stores_a_range_and_leaves_a_single_price_open(
    db_session, sample_activity, sample_location
) -> None:
    repo = ActivityPricingRepository(db_session)
    single = _create_pricing(
        repo,
        {
            "activity_id": str(sample_activity.id),
            "location_id": str(sample_location.id),
            "pricing_type": "per_class",
            "amount": "200",
        },
    )
    ranged = _create_pricing(
        repo,
        {
            "activity_id": str(sample_activity.id),
            "location_id": str(sample_location.id),
            "pricing_type": "per_hour",
            "amount": "200",
            "amount_max": "300",
        },
    )
    repo.create(single)
    repo.create(ranged)
    db_session.flush()
    assert single.amount_max is None
    assert ranged.amount == Decimal(200)
    assert ranged.amount_max == Decimal(300)
    assert _serialize_pricing(ranged)["amount_max"] == Decimal(300)


def test_create_rejects_a_bound_that_is_not_higher(
    db_session, sample_activity, sample_location
) -> None:
    body = {
        "activity_id": str(sample_activity.id),
        "location_id": str(sample_location.id),
        "pricing_type": "per_class",
        "amount": "200",
        "amount_max": "200",
    }
    with pytest.raises(ValidationError) as exc_info:
        _create_pricing(ActivityPricingRepository(db_session), body)
    assert exc_info.value.field == "amount_max"


def test_free_rejects_an_upper_bound(
    db_session, sample_activity, sample_location
) -> None:
    body = {
        "activity_id": str(sample_activity.id),
        "location_id": str(sample_location.id),
        "pricing_type": "free",
        "amount_max": "10",
    }
    with pytest.raises(ValidationError) as exc_info:
        _create_pricing(ActivityPricingRepository(db_session), body)
    assert exc_info.value.field == "amount_max"


def test_update_sets_and_clears_the_upper_bound(
    db_session, sample_activity, sample_location
) -> None:
    repo = ActivityPricingRepository(db_session)
    pricing = _create_pricing(
        repo,
        {
            "activity_id": str(sample_activity.id),
            "location_id": str(sample_location.id),
            "pricing_type": "per_month",
            "amount": "3800",
        },
    )
    repo.create(pricing)
    db_session.flush()
    _update_pricing(repo, pricing, {"amount_max": "4200"})
    assert pricing.amount_max == Decimal(4200)
    _update_pricing(repo, pricing, {"amount_max": None})
    assert pricing.amount_max is None
    with pytest.raises(ValidationError):
        _update_pricing(repo, pricing, {"amount": "5000", "amount_max": "4200"})


def test_database_rejects_an_upper_bound_that_is_not_higher(
    db_session, sample_activity, sample_location
) -> None:
    db_session.add(
        ActivityPricing(
            activity_id=sample_activity.id,
            location_id=sample_location.id,
            pricing_type=PricingType.PER_CLASS,
            amount=Decimal(200),
            amount_max=Decimal(200),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_shape_treats_a_missing_upper_bound_as_one_price() -> None:
    assert pricing_shape({"amount": "10", "amount_max": "12"})["amount_max"] == "12.00"
    assert pricing_shape({"amount": "10"})["amount_max"] is None


def test_enrichment_keeps_a_higher_bound_and_blocks_a_bad_one() -> None:
    proposed = {"pricing_type": "per_class", "amount": "200", "amount_max": "300"}
    fields = pricing_fields(proposed, {})
    assert fields["amount_max"] == Decimal(300)
    assert pricing_fields(proposed, {"amount_max": ""})["amount_max"] is None
    blockers = row_blockers(
        "create_pricing",
        {"pricing_type": "per_class", "amount": "200", "amount_max": "200"},
        status="pending",
        activity_names=["Painting"],
        venues=[],
    )
    assert any(item["field"] == "amount_max" for item in blockers)


def _seed_prices(engine) -> dict[str, str]:
    token = uuid4().hex[:8]
    with Session(engine) as session:
        area = GeographicArea(
            name=f"Range area {token}", level="neighbourhood", active=True
        )
        category = ActivityCategory(name=f"Range category {token}", display_order=0)
        org = Organization(
            name=f"Range club {token}",
            manager_id=_MANAGER,
            review_status="approved",
        )
        session.add_all([area, category, org])
        session.flush()
        location = Location(
            org_id=org.id,
            area_id=area.id,
            address=f"{token} Range Road",
            lat=Decimal("22.280000"),
            lng=Decimal("114.150000"),
        )
        session.add(location)
        session.flush()

        def listing(name: str, amount: str, amount_max: str | None) -> Activity:
            activity = Activity(
                org_id=org.id,
                category_id=category.id,
                name=name,
                age_range=Range(4, 8, bounds="[]"),
            )
            session.add(activity)
            session.flush()
            session.add(
                ActivityPricing(
                    activity_id=activity.id,
                    location_id=location.id,
                    pricing_type=PricingType.PER_CLASS,
                    amount=Decimal(amount),
                    amount_max=None if amount_max is None else Decimal(amount_max),
                )
            )
            schedule = ActivitySchedule(
                activity_id=activity.id,
                location_id=location.id,
                schedule_type=ScheduleType.WEEKLY,
                languages=["en"],
            )
            session.add(schedule)
            session.flush()
            session.add(
                ActivityScheduleEntry(
                    schedule_id=schedule.id,
                    day_of_week_utc=1,
                    start_minutes_utc=120,
                    end_minutes_utc=180,
                )
            )
            return activity

        ranged = listing("Ranged class", "200", "400")
        cheap = listing("Cheap class", "100", None)
        session.commit()
        return {
            "org_id": str(org.id),
            "area_id": str(area.id),
            "category_id": str(category.id),
            "ranged_id": str(ranged.id),
            "cheap_id": str(cheap.id),
        }


def _delete_prices(engine, seeded: dict[str, str]) -> None:
    with Session(engine) as session:
        org = session.get(Organization, seeded["org_id"])
        if org is not None:
            session.delete(org)
        for model, key in (
            (GeographicArea, "area_id"),
            (ActivityCategory, "category_id"),
        ):
            row = session.get(model, seeded[key])
            if row is not None:
                session.delete(row)
        session.commit()


@pytest.fixture
def ranged_search(monkeypatch, test_engine):
    monkeypatch.setattr("app.api.search.get_engine", lambda: test_engine)
    data = _seed_prices(test_engine)
    yield data
    _delete_prices(test_engine, data)


def _ids(filters: ActivitySearchFilters) -> list[str]:
    return [item.activity.id for item in fetch_search_response(filters).items]


def test_search_matches_an_overlapping_range_and_sorts_by_the_lower_bound(
    ranged_search,
) -> None:
    org_id = UUID(ranged_search["org_id"])
    shared = {
        "org_ids": [org_id],
        "apply_area_scope": False,
        "limit": 20,
    }
    assert _ids(ActivitySearchFilters(price_min=Decimal(350), **shared)) == [
        ranged_search["ranged_id"]
    ]
    assert _ids(ActivitySearchFilters(price_max=Decimal(150), **shared)) == [
        ranged_search["cheap_id"]
    ]
    both = _ids(
        ActivitySearchFilters(
            price_min=Decimal(250),
            price_max=Decimal(300),
            **shared,
        )
    )
    assert both == [ranged_search["ranged_id"]]
    assert _ids(ActivitySearchFilters(class_price_max=Decimal(150), **shared)) == [
        ranged_search["cheap_id"]
    ]
    ordered = _ids(ActivitySearchFilters(sort="price", **shared))
    assert ordered == [ranged_search["cheap_id"], ranged_search["ranged_id"]]
    card = dump_search_response(
        fetch_search_response(ActivitySearchFilters(view="card", **shared)),
        "card",
    )
    by_id = {row["activity"]["id"]: row for row in card["items"]}
    assert by_id[ranged_search["ranged_id"]]["pricing"]["amount_max"] == Decimal(400)
    assert "amount_max" not in by_id[ranged_search["cheap_id"]]["pricing"]
