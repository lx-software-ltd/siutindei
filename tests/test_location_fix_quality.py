"""Location quality rules: pins, addresses, geocode-on-apply, and candidates."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.db.models import (
    Activity,
    ActivityLocation,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.location_fix import LocationFixProposal
from app.exceptions import ValidationError
from app.services.location_fix_districts import district_key, pin_is_outside
from app.services.location_fix_query import list_proposals
from app.services.location_fix_scan import start_location_scan
from app.services.location_fixes import decide_bulk, decide_proposal
from psycopg.types.range import Range
from sqlalchemy import select

_MANAGER = "00000000-0000-0000-0000-000000000001"
_CENTRAL = Decimal("22.280000")
_CENTRAL_LNG = Decimal("114.150000")


def test_central_pin_is_outside_sham_shui_po() -> None:
    assert pin_is_outside(22.28, 114.15, "sham-shui-po")
    assert not pin_is_outside(22.28, 114.15, "central-and-western")
    assert pin_is_outside(0, 0, "central-and-western")


def test_shared_boundary_pins_stay_inside() -> None:
    assert not pin_is_outside(22.3245, 114.1685, "yau-tsim-mong")
    assert not pin_is_outside(22.3245, 114.1685, "sham-shui-po")
    assert not pin_is_outside(22.265, 114.237, "eastern")
    assert not pin_is_outside(22.265, 114.237, "southern")


def test_district_key_requires_hong_kong(db_session) -> None:
    country = _country(db_session, "Hong Kong", "HK")
    parent = GeographicArea(
        name="Hong Kong Island",
        level="region",
        parent_id=country.id,
        active=True,
    )
    db_session.add(parent)
    db_session.flush()
    child = GeographicArea(
        name="灣仔",
        level="district",
        parent_id=parent.id,
        active=True,
    )
    db_session.add(child)
    db_session.flush()
    assert district_key([child, parent]) is None
    assert district_key([child, parent, country]) == "wan-chai"
    singapore = _country(db_session, "Singapore", "SG")
    north = GeographicArea(
        name="North",
        level="district",
        parent_id=singapore.id,
        active=True,
    )
    db_session.add(north)
    db_session.flush()
    assert district_key([north, singapore]) is None


def _country(db_session, name: str, code: str) -> GeographicArea:
    area = GeographicArea(name=name, code=code, level="country", active=True)
    db_session.add(area)
    db_session.flush()
    return area


def _org(db_session, name: str = "Harbour Club") -> Organization:
    org = Organization(name=name, manager_id=_MANAGER, review_status="pending_review")
    db_session.add(org)
    db_session.flush()
    return org


def _area(
    db_session, name: str, parent: GeographicArea | None = None
) -> GeographicArea:
    area = GeographicArea(
        name=name,
        level="district",
        parent_id=None if parent is None else parent.id,
        active=True,
    )
    db_session.add(area)
    db_session.flush()
    return area


def _venue(db_session, org, area, address: str | None, **kwargs) -> Location:
    location = Location(org_id=org.id, area_id=area.id, address=address, **kwargs)
    db_session.add(location)
    db_session.flush()
    return location


def _rows(db_session, org) -> list[LocationFixProposal]:
    return list(
        db_session.scalars(
            select(LocationFixProposal).where(LocationFixProposal.org_id == org.id)
        ).all()
    )


def _pending(db_session, org) -> list[LocationFixProposal]:
    return [row for row in _rows(db_session, org) if row.status == "pending"]


def test_sweep_stores_the_address_and_apply_quantizes(db_session, monkeypatch) -> None:
    calls = {"count": 0}

    def _geocode(_address):
        calls["count"] += 1
        return 22.28000019, 114.1500004

    monkeypatch.setattr("app.services.location_fix_apply.geocode_address", _geocode)
    org = _org(db_session)
    area = _area(db_session, "Central and Western")
    venue = _venue(db_session, org, area, "8 Harbour Road", place_id="ChIJfixture")
    result, batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert batches == []
    assert result["created"] == 1
    assert calls["count"] == 0
    proposal = _rows(db_session, org)[0]
    assert proposal.kind == "update_location"
    assert proposal.source == "rule:missing_coordinates"
    assert proposal.proposed_location.get("lat") is None
    decide_proposal(db_session, proposal.id, "apply", "admin")
    assert calls["count"] == 1
    assert venue.lat == Decimal("22.280000")
    assert venue.lng == Decimal("114.150000")
    assert venue.place_id == "ChIJfixture"


def test_apply_geocodes_when_the_sweep_did_not(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.location_fix_apply.geocode_address",
        lambda _address: (22.281, 114.151),
    )
    org = _org(db_session)
    area = _area(db_session, "Central and Western")
    venue = _venue(db_session, org, area, "8 Harbour Road")
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    proposal = _rows(db_session, org)[0]
    assert proposal.proposed_location.get("lat") is None
    decide_proposal(db_session, proposal.id, "apply", "admin")
    assert venue.lat == Decimal("22.281000")
    assert venue.place_id is None


def test_apply_refuses_a_changed_address(db_session) -> None:
    org = _org(db_session)
    area = _area(db_session, "Central and Western")
    venue = _venue(db_session, org, area, "8 Harbour Road")
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    proposal = _rows(db_session, org)[0]
    venue.address = "9 Pier Street"
    db_session.flush()
    with pytest.raises(ValidationError) as exc_info:
        decide_proposal(db_session, proposal.id, "apply", "admin")
    assert exc_info.value.field == "address"


def test_apply_does_not_overwrite_a_stored_pin(db_session, monkeypatch) -> None:
    def _geocode(_address):
        raise AssertionError("stored pin must not be looked up")

    monkeypatch.setattr("app.services.location_fix_apply.geocode_address", _geocode)
    org = _org(db_session)
    area = _area(db_session, "Central and Western")
    venue = _venue(db_session, org, area, "8 Harbour Road")
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    proposal = _rows(db_session, org)[0]
    venue.lat = Decimal("22.111111")
    venue.lng = Decimal("114.222222")
    db_session.flush()
    decide_proposal(db_session, proposal.id, "apply", "admin")
    assert venue.lat == Decimal("22.111111")
    assert venue.lng == Decimal("114.222222")
    assert proposal.status == "applied"


def test_bulk_apply_does_not_geocode(db_session, monkeypatch) -> None:
    calls = {"count": 0}

    def _geocode(_address):
        calls["count"] += 1
        return 22.28, 114.15

    monkeypatch.setattr("app.services.location_fix_apply.geocode_address", _geocode)
    org = _org(db_session)
    area = _area(db_session, "Central and Western")
    venue = _venue(db_session, org, area, "8 Harbour Road")
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    proposal = _pending(db_session, org)[0]
    result = decide_bulk(
        db_session, {"action": "apply", "ids": [str(proposal.id)]}, "admin"
    )
    assert result["failed"] == 1
    assert result["failures"][0]["message"] == "Look up this map pin on its own"
    assert calls["count"] == 0
    assert venue.lat is None
    decide_proposal(db_session, proposal.id, "apply", "admin")
    assert calls["count"] == 1
    assert venue.lat == Decimal("22.280000")


def test_empty_address_and_outside_pin(db_session) -> None:
    org = _org(db_session)
    hk = _country(db_session, "Hong Kong", "HK")
    central = _area(db_session, "Central and Western", hk)
    sham = _area(db_session, "深水埗", hk)
    empty = _venue(
        db_session,
        org,
        central,
        None,
        lat=_CENTRAL,
        lng=_CENTRAL_LNG,
        place_id="ChIJfixture",
    )
    outside = _venue(
        db_session,
        org,
        sham,
        "10 Sham Street",
        lat=_CENTRAL,
        lng=_CENTRAL_LNG,
        place_id="ChIJoutside",
    )
    no_place = _venue(
        db_session,
        org,
        central,
        "1 Harbour Road",
        lat=_CENTRAL,
        lng=_CENTRAL_LNG,
    )
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    by_id = {row.entity_id: row for row in _rows(db_session, org)}
    assert by_id[empty.id].source == "rule:empty_address"
    assert by_id[outside.id].source == "rule:pin_outside_area"
    assert no_place.id not in by_id


def test_dismissed_pin_matches_coordinates_only(db_session) -> None:
    org = _org(db_session)
    hk = _country(db_session, "Hong Kong", "HK")
    sham = _area(db_session, "深水埗", hk)
    venue = _venue(
        db_session,
        org,
        sham,
        "10 Sham Street",
        lat=_CENTRAL,
        lng=_CENTRAL_LNG,
    )
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    decide_proposal(db_session, _pending(db_session, org)[0].id, "dismiss", "admin")
    again, _batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert again["skipped"] >= 1
    assert _pending(db_session, org) == []
    venue.lat = Decimal("22.500000")
    venue.lng = Decimal("114.200000")
    db_session.flush()
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    pending = _pending(db_session, org)
    assert len(pending) == 1
    assert pending[0].source == "rule:pin_outside_area"


def test_dismissed_empty_address_does_not_block_a_later_pin(db_session) -> None:
    org = _org(db_session)
    hk = _country(db_session, "Hong Kong", "HK")
    sham = _area(db_session, "深水埗", hk)
    venue = _venue(db_session, org, sham, None, lat=_CENTRAL, lng=_CENTRAL_LNG)
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    decide_proposal(db_session, _pending(db_session, org)[0].id, "dismiss", "admin")
    venue.address = "10 Sham Street"
    db_session.flush()
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    pending = _pending(db_session, org)
    assert len(pending) == 1
    assert pending[0].source == "rule:pin_outside_area"


def test_dismissed_geocode_is_not_repeated(db_session) -> None:
    org = _org(db_session)
    area = _area(db_session, "Central and Western")
    _venue(db_session, org, area, "8 Harbour Road")
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    decide_proposal(db_session, _rows(db_session, org)[0].id, "dismiss", "admin")
    result, _batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert result["skipped"] >= 1
    assert _pending(db_session, org) == []


def test_address_search_finds_a_location_proposal(db_session) -> None:
    org = _org(db_session, "Quiet Club")
    hk = _country(db_session, "Hong Kong", "HK")
    sham = _area(db_session, "深水埗", hk)
    _venue(
        db_session,
        org,
        sham,
        "8 Harbour Road",
        lat=_CENTRAL,
        lng=_CENTRAL_LNG,
    )
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    found = list_proposals(
        db_session,
        status="pending",
        entity_type=None,
        kind=None,
        source=None,
        org_id=None,
        query="Harbour Road",
        cursor=None,
        limit=50,
    )
    assert len(found["items"]) == 1
    assert found["items"][0]["entity_type"] == "location"
    assert found["items"][0]["current_label"] == "Pin outside district"


def test_apply_links_a_named_candidate(db_session, sample_activity_category) -> None:
    org = _org(db_session)
    area = _area(db_session, "Central and Western")
    first = _venue(
        db_session,
        org,
        area,
        "8 Harbour Road",
        lat=_CENTRAL,
        lng=_CENTRAL_LNG,
        place_id="ChIJfirst",
    )
    second = _venue(
        db_session,
        org,
        area,
        "9 Pier Street",
        lat=_CENTRAL,
        lng=_CENTRAL_LNG,
        place_id="ChIJsecond",
    )
    activity = Activity(
        org_id=org.id,
        category_id=sample_activity_category.id,
        name="Art Class",
        age_range=Range(5, 12, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()
    proposal = LocationFixProposal(
        entity_type="activity",
        entity_id=activity.id,
        org_id=org.id,
        kind="unresolved",
        source="model",
        proposed_location={
            "candidates": [
                {"location_id": str(first.id), "address": first.address},
                {"location_id": str(second.id), "address": second.address},
            ]
        },
        rationale="Model named more than one venue",
    )
    db_session.add(proposal)
    db_session.flush()
    with pytest.raises(ValidationError) as exc_info:
        decide_proposal(
            db_session,
            proposal.id,
            "apply",
            "admin",
            target_location_id="00000000-0000-0000-0000-000000000099",
        )
    assert exc_info.value.field == "target_location_id"


def test_apply_links_the_chosen_candidate(db_session, sample_activity_category) -> None:
    org = _org(db_session, "Candidate Club")
    area = _area(db_session, "Central and Western")
    first = _venue(
        db_session,
        org,
        area,
        "8 Harbour Road",
        lat=_CENTRAL,
        lng=_CENTRAL_LNG,
        place_id="ChIJfirst",
    )
    second = _venue(
        db_session,
        org,
        area,
        "9 Pier Street",
        lat=_CENTRAL,
        lng=_CENTRAL_LNG,
        place_id="ChIJsecond",
    )
    activity = Activity(
        org_id=org.id,
        category_id=sample_activity_category.id,
        name="Art Class",
        age_range=Range(5, 12, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()
    proposal = LocationFixProposal(
        entity_type="activity",
        entity_id=activity.id,
        org_id=org.id,
        kind="unresolved",
        source="model",
        proposed_location={
            "candidates": [
                {"location_id": str(first.id), "address": first.address},
                {"location_id": str(second.id), "address": second.address},
            ]
        },
    )
    db_session.add(proposal)
    db_session.flush()
    decide_proposal(
        db_session, proposal.id, "apply", "admin", target_location_id=first.id
    )
    assert db_session.get(ActivityLocation, (activity.id, first.id)) is not None
    assert proposal.kind == "unresolved"
    assert proposal.status == "applied"
