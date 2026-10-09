"""Apply, dismiss, geocode, and model proposals for venues."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from app.db.models import (
    Activity,
    ActivityLocation,
    GeographicArea,
    Location,
    LocationFixProposal,
    LocationScanRun,
    Organization,
)
from app.exceptions import ValidationError
from app.services import location_fixes as location_fix_service
from app.services.location_fix_geocode import geocode_address
from app.services.location_fix_model import store_model_items
from app.services.location_fix_prompt import build_organization_prompt
from app.services.location_fixes import decide_bulk, decide_proposal
from psycopg.types.range import Range
from sqlalchemy import select

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _org(db_session) -> Organization:
    org = Organization(name="Harbour Club", manager_id=_MANAGER)
    db_session.add(org)
    db_session.flush()
    return org


def _area(db_session, name: str = "灣仔") -> GeographicArea:
    area = GeographicArea(name=name, level="district", active=True)
    db_session.add(area)
    db_session.flush()
    return area


def test_apply_create_geocodes_and_links_orphan_activities(
    db_session, sample_activity_category, monkeypatch
) -> None:
    org = _org(db_session)
    area = _area(db_session)
    activity = Activity(
        org_id=org.id,
        category_id=sample_activity_category.id,
        name="Swim Class",
        age_range=Range(5, 12, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()
    proposal = LocationFixProposal(
        entity_type="organization",
        entity_id=org.id,
        org_id=org.id,
        kind="create_location",
        source="model",
        proposed_location={"address": "10 Harbour Road", "area_id": str(area.id)},
        status="pending",
    )
    db_session.add_all([activity, proposal])
    db_session.add(
        LocationFixProposal(
            entity_type="activity",
            entity_id=activity.id,
            org_id=org.id,
            kind="unresolved",
            source="rule:no_venue",
            status="pending",
        )
    )
    db_session.flush()
    monkeypatch.setattr(
        "app.services.location_fix_apply.geocode_address",
        lambda _address: (22.28, 114.17),
    )
    decide_proposal(db_session, proposal.id, "apply", "admin")
    location = db_session.scalars(
        select(Location).where(Location.org_id == org.id)
    ).one()
    assert location.address == "10 Harbour Road"
    assert float(location.lat) == 22.28
    assert float(location.lng) == 114.17
    assert db_session.get(ActivityLocation, (activity.id, location.id)) is not None
    pending = db_session.scalars(
        select(LocationFixProposal).where(
            LocationFixProposal.org_id == org.id,
            LocationFixProposal.status == "pending",
        )
    ).all()
    assert pending == []
    assert proposal.status == "applied"


def test_apply_link_inserts_the_join(db_session, sample_activity_category) -> None:
    org = _org(db_session)
    area = _area(db_session)
    venue = Location(
        org_id=org.id,
        area_id=area.id,
        address="1 Harbour Road",
        lat=Decimal("22.280000"),
        lng=Decimal("114.150000"),
    )
    activity = Activity(
        org_id=org.id,
        category_id=sample_activity_category.id,
        name="Swim Class",
        age_range=Range(5, 12, bounds="[]"),
    )
    db_session.add_all([venue, activity])
    db_session.flush()
    proposal = LocationFixProposal(
        entity_type="activity",
        entity_id=activity.id,
        org_id=org.id,
        kind="link_existing",
        source="rule:name_area",
        target_location_id=venue.id,
        status="pending",
    )
    db_session.add(proposal)
    db_session.flush()
    payload = decide_proposal(db_session, proposal.id, "apply", "admin")
    assert db_session.get(ActivityLocation, (activity.id, venue.id)) is not None
    assert proposal.status == "applied"
    assert payload["current_label"] == "1 of 1 venues"


def test_unresolved_cannot_be_applied(db_session) -> None:
    org = _org(db_session)
    proposal = LocationFixProposal(
        entity_type="activity",
        entity_id=org.id,
        org_id=org.id,
        kind="unresolved",
        source="model",
        status="pending",
    )
    db_session.add(proposal)
    db_session.flush()
    with pytest.raises(ValidationError) as exc_info:
        decide_proposal(db_session, proposal.id, "apply", "admin")
    assert exc_info.value.field == "kind"


def test_bulk_matched_counts_only_rows_it_decides(db_session, monkeypatch) -> None:
    monkeypatch.setattr(location_fix_service, "_MAX_BULK", 1)
    first = _org(db_session)
    second = Organization(name="Second Club", manager_id=_MANAGER)
    db_session.add(second)
    db_session.flush()
    db_session.add_all(
        [
            LocationFixProposal(
                entity_type="organization",
                entity_id=first.id,
                org_id=first.id,
                kind="unresolved",
                source="model",
                status="pending",
            ),
            LocationFixProposal(
                entity_type="organization",
                entity_id=second.id,
                org_id=second.id,
                kind="unresolved",
                source="model",
                status="pending",
            ),
        ]
    )
    db_session.flush()
    result = decide_bulk(db_session, {"action": "dismiss"}, "admin")
    assert result["matched"] == 1
    assert result["decided"] == 1
    assert result["truncated"] is True
    pending = db_session.scalars(
        select(LocationFixProposal).where(
            LocationFixProposal.status == "pending",
            LocationFixProposal.org_id.in_([first.id, second.id]),
        )
    ).all()
    assert len(pending) == 1


def test_bulk_dismiss_respects_org_id(db_session) -> None:
    keep = _org(db_session)
    other = Organization(name="Other Club", manager_id=_MANAGER)
    db_session.add(other)
    db_session.flush()
    db_session.add_all(
        [
            LocationFixProposal(
                entity_type="organization",
                entity_id=keep.id,
                org_id=keep.id,
                kind="unresolved",
                source="model",
                status="pending",
            ),
            LocationFixProposal(
                entity_type="organization",
                entity_id=other.id,
                org_id=other.id,
                kind="unresolved",
                source="model",
                status="pending",
            ),
        ]
    )
    db_session.flush()
    result = decide_bulk(
        db_session,
        {"action": "dismiss", "org_id": str(keep.id)},
        "admin",
    )
    assert result["decided"] == 1
    statuses = {
        row.org_id: row.status
        for row in db_session.scalars(
            select(LocationFixProposal).where(
                LocationFixProposal.org_id.in_([keep.id, other.id])
            )
        ).all()
    }
    assert statuses[keep.id] == "dismissed"
    assert statuses[other.id] == "pending"


def _run(db_session) -> LocationScanRun:
    run = LocationScanRun(status="done", review_scope="all")
    db_session.add(run)
    db_session.flush()
    return run


def test_model_create_location_uses_nominatim(db_session, monkeypatch) -> None:
    org = _org(db_session)
    area = _area(db_session, "灣仔")
    run_id = _run(db_session).id
    monkeypatch.setattr(
        "app.services.location_fix_model.geocode_address",
        lambda _address: (22.11, 114.22),
    )
    store_model_items(
        db_session,
        run_id,
        "organization",
        [str(org.id)],
        {
            "items": [
                {
                    "entity_id": str(org.id),
                    "kind": "create_location",
                    "address": "8 Harbour Road",
                    "area_name": "灣仔",
                    "confidence": 0.8,
                    "rationale": "Named on the source page",
                }
            ]
        },
    )
    proposal = db_session.scalars(
        select(LocationFixProposal).where(LocationFixProposal.org_id == org.id)
    ).one()
    assert proposal.kind == "create_location"
    assert proposal.proposed_location["area_id"] == str(area.id)
    assert proposal.proposed_location["lat"] == 22.11
    assert proposal.source == "model"
    assert proposal.status == "pending"


def test_model_activity_links_one_index(db_session, sample_activity_category) -> None:
    org = _org(db_session)
    area = _area(db_session)
    first = Location(
        org_id=org.id,
        area_id=area.id,
        address="A Street",
        lat=Decimal("22.1"),
        lng=Decimal("114.1"),
    )
    second = Location(
        org_id=org.id,
        area_id=area.id,
        address="B Street",
        lat=Decimal("22.2"),
        lng=Decimal("114.2"),
    )
    activity = Activity(
        org_id=org.id,
        category_id=sample_activity_category.id,
        name="Art",
        age_range=Range(5, 12, bounds="[]"),
    )
    db_session.add_all([first, second, activity])
    db_session.flush()
    store_model_items(
        db_session,
        _run(db_session).id,
        "activity",
        [str(activity.id)],
        {
            "items": [
                {
                    "entity_id": str(activity.id),
                    "kind": "link_existing",
                    "location_indexes": [1],
                    "confidence": 0.6,
                    "rationale": "Description names B Street",
                }
            ]
        },
    )
    proposal = db_session.scalars(
        select(LocationFixProposal).where(LocationFixProposal.org_id == org.id)
    ).one()
    assert proposal.target_location_id == second.id
    assert proposal.kind == "link_existing"


def test_prompt_redacts_contacts(db_session) -> None:
    org = Organization(
        name="Harbour Club",
        manager_id=_MANAGER,
        description="Email desk@example.com or call +852 2123 4567",
    )
    db_session.add(org)
    db_session.flush()
    _system, user = build_organization_prompt(db_session, [org])
    assert "desk@example.com" not in user
    assert "2123 4567" not in user
    assert "[redacted-email]" in user
    assert "[redacted-phone]" in user


def test_geocode_reads_the_first_nominatim_hit(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.location_fix_geocode._get_nominatim_headers",
        lambda: {"User-Agent": "test", "Referer": "https://example.com"},
    )

    def fake_invoke(*_args, **_kwargs):
        return {
            "status": 200,
            "body": json.dumps([{"lat": "22.28", "lon": "114.15"}]),
        }

    monkeypatch.setattr(
        "app.services.location_fix_geocode.http_invoke",
        fake_invoke,
    )
    assert geocode_address("10 Harbour Road") == (22.28, 114.15)
