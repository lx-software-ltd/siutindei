"""Venue sweeps: rules, auto-link, and model queue."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.db.models import (
    Activity,
    ActivityLocation,
    ActivityPricing,
    GeographicArea,
    Location,
    LocationFixProposal,
    LocationScanRun,
    Organization,
)
from app.db.models.category_scan import CategoryScanRun
from app.db.models.enums import PricingType
from app.exceptions import ValidationError
from app.services.location_fix_query import load_settings
from app.services.location_fix_scan import start_location_scan
from psycopg.types.range import Range
from sqlalchemy import select

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _org(db_session, name: str, review_status: str = "pending_review") -> Organization:
    org = Organization(
        name=name,
        manager_id=_MANAGER,
        review_status=review_status,
    )
    db_session.add(org)
    db_session.flush()
    return org


def _area(db_session, name: str = "深水埗") -> GeographicArea:
    area = GeographicArea(name=name, level="district", active=True)
    db_session.add(area)
    db_session.flush()
    return area


def _location(db_session, org, area, address: str) -> Location:
    location = Location(
        org_id=org.id,
        area_id=area.id,
        address=address,
        lat=Decimal("22.280000"),
        lng=Decimal("114.150000"),
    )
    db_session.add(location)
    db_session.flush()
    return location


def _activity(db_session, org, category, name: str) -> Activity:
    activity = Activity(
        org_id=org.id,
        category_id=category.id,
        name=name,
        age_range=Range(5, 12, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()
    return activity


def test_single_location_is_linked_immediately(
    db_session, sample_activity_category
) -> None:
    org = _org(db_session, "Harbour Club")
    area = _area(db_session)
    venue = _location(db_session, org, area, "1 Harbour Road")
    activity = _activity(db_session, org, sample_activity_category, "Swim Class")
    result = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert result[0]["auto_applied"] == 1
    assert result[0]["queued_for_model"] == 0
    assert result[1] == []
    join = db_session.get(ActivityLocation, (activity.id, venue.id))
    assert join is not None
    proposal = db_session.scalars(select(LocationFixProposal)).one()
    assert proposal.status == "applied"
    assert proposal.source == "rule:single_location"


def test_pending_scope_skips_approved_orgs(
    db_session, sample_activity_category
) -> None:
    pending = _org(db_session, "Pending Venue")
    approved = _org(db_session, "Approved Venue", "approved")
    _activity(db_session, pending, sample_activity_category, "Pending Class")
    _activity(db_session, approved, sample_activity_category, "Approved Class")
    result, batches = start_location_scan(db_session, review_scope="pending_review")
    queued_ids = [entity_id for batch in batches for entity_id in batch["entity_ids"]]
    assert str(pending.id) in queued_ids
    assert str(approved.id) not in queued_ids
    assert result["queued_for_model"] >= 1
    rows = list(
        db_session.scalars(
            select(LocationFixProposal).where(LocationFixProposal.org_id == pending.id)
        ).all()
    )
    assert len(rows) == 1
    assert rows[0].source == "rule:no_venue"
    assert rows[0].org_id == pending.id
    approved_queued = [
        entity_id
        for batch in batches
        for entity_id in batch["entity_ids"]
        if entity_id == str(approved.id)
    ]
    assert approved_queued == []


def test_sweep_all_includes_approved_orgs(db_session) -> None:
    approved = _org(db_session, "Approved Venue", "approved")
    result, batches = start_location_scan(
        db_session, review_scope="all", org_id=approved.id
    )
    assert result["queued_for_model"] == 1
    assert batches[0]["entity_type"] == "organization"


def test_pricing_location_stays_pending(db_session, sample_activity_category) -> None:
    org = _org(db_session, "Two Venues")
    area = _area(db_session)
    first = _location(db_session, org, area, "1 First Street")
    _location(db_session, org, area, "2 Second Street")
    activity = _activity(db_session, org, sample_activity_category, "Swim Class")
    db_session.add(
        ActivityPricing(
            activity_id=activity.id,
            location_id=first.id,
            pricing_type=PricingType.PER_CLASS,
            amount=Decimal("100.00"),
            currency="HKD",
        )
    )
    db_session.flush()
    result, batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert result["created"] == 1
    assert batches == []
    proposal = db_session.scalars(select(LocationFixProposal)).one()
    assert proposal.source == "rule:pricing_schedule"
    assert proposal.target_location_id == first.id
    assert proposal.status == "pending"
    assert db_session.get(ActivityLocation, (activity.id, first.id)) is None


def test_name_area_matches_one_district(db_session, sample_activity_category) -> None:
    org = _org(db_session, "District Club")
    sham = _area(db_session, "深水埗")
    other = _area(db_session, "灣仔")
    match = _location(db_session, org, sham, "10 Sham Street")
    _location(db_session, org, other, "10 Wan Chai Road")
    activity = _activity(db_session, org, sample_activity_category, "Swim 深水埗")
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    proposal = db_session.scalars(
        select(LocationFixProposal).where(LocationFixProposal.entity_id == activity.id)
    ).one()
    assert proposal.source == "rule:name_area"
    assert proposal.target_location_id == match.id


def test_dismissed_single_venue_is_not_linked_again(
    db_session, sample_activity_category
) -> None:
    org = _org(db_session, "Harbour Club")
    area = _area(db_session)
    venue = _location(db_session, org, area, "1 Harbour Road")
    activity = _activity(db_session, org, sample_activity_category, "Swim Class")
    db_session.add(
        LocationFixProposal(
            entity_type="activity",
            entity_id=activity.id,
            org_id=org.id,
            kind="link_existing",
            source="rule:single_location",
            target_location_id=venue.id,
            status="dismissed",
        )
    )
    db_session.flush()
    result, _batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert result["skipped"] == 1
    assert result["auto_applied"] == 0
    assert db_session.get(ActivityLocation, (activity.id, venue.id)) is None


def test_unknown_scope_is_rejected(db_session) -> None:
    with pytest.raises(ValidationError) as exc_info:
        start_location_scan(db_session, review_scope="nope")
    assert exc_info.value.field == "review_scope"


def test_location_budget_is_separate_from_category_checks(db_session) -> None:
    db_session.add(CategoryScanRun(status="done", cost_usd=Decimal(400)))
    load_settings(db_session).monthly_cost_limit_usd = Decimal(50)
    org = _org(db_session, "Still In Budget")
    db_session.flush()
    result, batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert batches
    assert result["queued_for_model"] == 1


def test_location_budget_blocks_its_own_spend(db_session) -> None:
    load_settings(db_session).monthly_cost_limit_usd = Decimal(50)
    db_session.add(
        LocationScanRun(
            status="done",
            review_scope="all",
            cost_usd=Decimal(50),
        )
    )
    db_session.flush()
    with pytest.raises(ValidationError) as exc_info:
        start_location_scan(db_session, review_scope="all")
    assert exc_info.value.field == "monthly_cost_limit_usd"
