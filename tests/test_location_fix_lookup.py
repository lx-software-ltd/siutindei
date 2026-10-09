"""Pin lookup grades and the apply rules that read them."""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.db.models import (
    GeographicArea,
    Location,
    LocationFixProposal,
    LocationScanRun,
    Organization,
)
from app.exceptions import ValidationError
from app.services.location_fix_lookup import _google, process_lookup_batch
from app.services.location_fix_scan import start_location_scan
from app.services.location_fixes import decide_bulk, decide_proposal
from sqlalchemy import select

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _org(db_session) -> Organization:
    org = Organization(
        name="Harbour Club",
        manager_id=_MANAGER,
        review_status="pending_review",
    )
    db_session.add(org)
    db_session.flush()
    return org


def _country(db_session) -> GeographicArea:
    area = GeographicArea(name="Hong Kong", code="HK", level="country", active=True)
    db_session.add(area)
    db_session.flush()
    return area


def _district(db_session, parent, name: str) -> GeographicArea:
    area = GeographicArea(
        name=name,
        level="district",
        parent_id=parent.id,
        active=True,
    )
    db_session.add(area)
    db_session.flush()
    return area


def _pinless(db_session, org, area, **kwargs) -> Location:
    venue = Location(
        org_id=org.id,
        area_id=area.id,
        address="8 Harbour Road",
        **kwargs,
    )
    db_session.add(venue)
    db_session.flush()
    return venue


def _proposal(db_session, org) -> LocationFixProposal:
    return db_session.scalars(
        select(LocationFixProposal).where(LocationFixProposal.org_id == org.id)
    ).one()


def test_precise_consistent_pin_can_be_bulk_applied(db_session, monkeypatch) -> None:
    def _geocode(_address):
        raise AssertionError("bulk apply must not geocode")

    monkeypatch.setattr("app.services.location_fix_apply.geocode_address", _geocode)
    org = _org(db_session)
    area = _district(db_session, _country(db_session), "Central and Western")
    venue = _pinless(db_session, org, area)
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    proposal = _proposal(db_session, org)
    proposal.proposed_location = {
        "address": "8 Harbour Road",
        "lat": 22.28,
        "lng": 114.15,
        "lookup": {
            "provider": "nominatim",
            "grade": "precise",
            "district_consistent": True,
        },
    }
    db_session.flush()
    result = decide_bulk(
        db_session, {"action": "apply", "ids": [str(proposal.id)]}, "admin"
    )
    assert result["failed"] == 0
    assert result["decided"] == 1
    assert venue.lat == Decimal("22.280000")
    assert venue.lng == Decimal("114.150000")


def test_street_grade_bulk_apply_asks_for_a_single_lookup(db_session) -> None:
    org = _org(db_session)
    area = _district(db_session, _country(db_session), "Central and Western")
    venue = _pinless(db_session, org, area)
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    proposal = _proposal(db_session, org)
    proposal.proposed_location = {
        "address": "8 Harbour Road",
        "lat": 22.28,
        "lng": 114.15,
        "lookup": {"grade": "street", "district_consistent": True},
    }
    db_session.flush()
    result = decide_bulk(
        db_session, {"action": "apply", "ids": [str(proposal.id)]}, "admin"
    )
    assert result["failures"][0]["message"] == "Look up this map pin on its own"
    assert venue.lat is None
    decide_proposal(db_session, proposal.id, "apply", "admin")
    assert venue.lat == Decimal("22.280000")


def test_inconsistent_pin_needs_an_area_on_single_apply(db_session) -> None:
    org = _org(db_session)
    country = _country(db_session)
    central = _district(db_session, country, "Central and Western")
    sham = _district(db_session, country, "Sham Shui Po")
    venue = _pinless(db_session, org, central)
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    proposal = _proposal(db_session, org)
    proposal.proposed_location = {
        "address": "8 Harbour Road",
        "lat": 22.33,
        "lng": 114.16,
        "lookup": {"grade": "precise", "district_consistent": False},
    }
    db_session.flush()
    with pytest.raises(ValidationError) as exc_info:
        decide_proposal(db_session, proposal.id, "apply", "admin")
    assert exc_info.value.message == "Pin is outside this district"
    decide_proposal(db_session, proposal.id, "apply", "admin", area_id=str(sham.id))
    assert venue.area_id == sham.id
    assert venue.lat == Decimal("22.330000")


def test_manual_pin_is_stored_inside_hong_kong(db_session) -> None:
    org = _org(db_session)
    area = _district(db_session, _country(db_session), "Central and Western")
    venue = _pinless(db_session, org, area)
    start_location_scan(db_session, review_scope="pending_review", org_id=org.id)
    proposal = _proposal(db_session, org)
    with pytest.raises(ValidationError) as outside:
        decide_proposal(db_session, proposal.id, "apply", "admin", lat=1.0, lng=103.0)
    assert outside.value.message == "Pin is outside Hong Kong"
    decide_proposal(db_session, proposal.id, "apply", "admin", lat=22.28, lng=114.15)
    assert venue.lat == Decimal("22.280000")
    assert proposal.proposed_location["lookup"]["grade"] == "manual"


def test_nominatim_lookup_is_queued_for_a_missing_pin(db_session) -> None:
    org = _org(db_session)
    area = _district(db_session, _country(db_session), "Central and Western")
    venue = _pinless(db_session, org, area, place_id="ChIJfixture")
    start_location_scan(
        db_session,
        review_scope="pending_review",
        entity_type="location",
        org_id=org.id,
    )
    result, batches = start_location_scan(
        db_session,
        review_scope="pending_review",
        entity_type="location",
        org_id=org.id,
        lookup="nominatim",
    )
    assert result["queued_for_lookup"] == 1
    assert batches[-1]["lookup"] == "nominatim"
    assert batches[-1]["entity_ids"] == [str(venue.id)]
    run = db_session.get(LocationScanRun, result["scan_run_id"])
    assert run is not None
    run.status = "done"
    proposal = _proposal(db_session, org)
    proposal.proposed_location = {
        **(proposal.proposed_location or {}),
        "lookup": {
            "provider": "nominatim",
            "grade": "precise",
            "looked_up_at": "2099-01-01T00:00:00+00:00",
        },
    }
    db_session.flush()
    again, later = start_location_scan(
        db_session,
        review_scope="pending_review",
        entity_type="location",
        org_id=org.id,
        lookup="nominatim",
    )
    assert again["queued_for_lookup"] == 0
    assert later == []


def test_google_lookup_requires_a_key_and_a_place_id(db_session, monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    org = _org(db_session)
    with pytest.raises(ValidationError) as exc_info:
        start_location_scan(
            db_session,
            review_scope="pending_review",
            org_id=org.id,
            lookup="google",
        )
    assert exc_info.value.field == "lookup"
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    area = _district(db_session, _country(db_session), "Central and Western")
    _pinless(db_session, org, area)
    start_location_scan(
        db_session,
        review_scope="pending_review",
        entity_type="location",
        org_id=org.id,
    )
    result, batches = start_location_scan(
        db_session,
        review_scope="pending_review",
        entity_type="location",
        org_id=org.id,
        lookup="google",
    )
    assert result["queued_for_lookup"] == 0
    assert batches == []


def test_google_place_details_keeps_the_key_in_a_header(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    seen: dict[str, object] = {}

    def fake_invoke(_method, url, **kwargs):
        seen["url"] = url
        seen["headers"] = kwargs.get("headers")
        return {
            "status": 200,
            "body": json.dumps(
                {
                    "id": "places/ChIJfixture",
                    "location": {"latitude": 22.28, "longitude": 114.15},
                    "businessStatus": "OPERATIONAL",
                }
            ),
        }

    monkeypatch.setattr("app.services.location_fix_lookup.http_invoke", fake_invoke)
    hit, cost, error = _google("ChIJfixture")
    assert error is None
    assert cost == Decimal("0.017")
    assert hit is not None
    assert hit["lat"] == 22.28
    assert "test-key" not in str(seen["url"])
    assert seen["headers"]["X-Goog-Api-Key"] == "test-key"


def test_nominatim_batch_pauses_between_requests(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(
        "app.services.location_fix_lookup.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )
    monkeypatch.setattr(
        "app.services.location_fix_lookup.lookup_address",
        lambda address: {
            "lat": 22.28,
            "lng": 114.15,
            "place_rank": 30,
            "type": "house",
            "display_name": address,
        },
    )
    venues = {
        "one": SimpleNamespace(id="one", area_id="area", address="8 Harbour Road"),
        "two": SimpleNamespace(id="two", area_id="area", address="9 Harbour Road"),
    }
    proposals = {
        key: SimpleNamespace(proposed_location={"address": venue.address})
        for key, venue in venues.items()
    }
    monkeypatch.setattr(
        "app.services.location_fix_lookup._venues",
        lambda _session, _ids: venues,
    )
    monkeypatch.setattr(
        "app.services.location_fix_lookup._pending",
        lambda _session, entity_id: proposals[entity_id],
    )
    monkeypatch.setattr(
        "app.services.location_fix_lookup.area_chains",
        lambda _session, _ids: {},
    )
    monkeypatch.setattr(
        "app.services.location_fix_lookup._finish_batch",
        lambda *_args, **_kwargs: None,
    )

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def commit(self):
            return None

    monkeypatch.setattr(
        "app.services.location_fix_lookup.Session", lambda _engine: _Session()
    )
    monkeypatch.setattr("app.services.location_fix_lookup.get_engine", lambda: object())
    assert process_lookup_batch(uuid4(), "nominatim", ["one", "two"], message_id="m")
    assert sleeps == [2.2]
    assert proposals["one"].proposed_location["lookup"]["grade"] == "precise"
