"""Hong Kong neighbourhood catalog and leaf location areas."""

from __future__ import annotations

import pytest
from app.api.admin_imports_lookups import lookup_district_area_id
from app.api.admin_resource_location import _create_location
from app.data.hk_neighbourhoods import (
    HK_DISTRICTS,
    NEIGHBOURHOODS,
    assign_in_district,
    distance_km,
    nearest_in_district,
)
from app.db.models import GeographicArea, Location, LocationFixProposal, Organization
from app.db.repositories import LocationRepository
from app.exceptions import ValidationError
from app.services.area_assignment import resolve_leaf
from app.services.location_fixes import decide_proposal
from sqlalchemy import select


def test_every_hong_kong_district_has_neighbourhoods() -> None:
    covered = {item.district for item in NEIGHBOURHOODS}
    assert covered == set(HK_DISTRICTS)
    assert len(NEIGHBOURHOODS) >= 18


def test_neighbourhood_names_and_ids_are_unique() -> None:
    english = [item.name.casefold() for item in NEIGHBOURHOODS]
    chinese = [item.name_zh for item in NEIGHBOURHOODS]
    wizard_ids = [item.wizard_id for item in NEIGHBOURHOODS]
    area_ids = [item.id for item in NEIGHBOURHOODS]
    assert len(english) == len(set(english))
    assert len(chinese) == len(set(chinese))
    assert len(wizard_ids) == len(set(wizard_ids))
    assert len(area_ids) == len(set(area_ids))


def test_nearest_pin_stays_inside_its_district() -> None:
    central = nearest_in_district("Central and Western", 22.282, 114.158)
    assert central is not None
    assert central.name == "Central"
    assert central.district == "Central and Western"
    unpinned = nearest_in_district("Wan Chai", None, None)
    assert unpinned is not None
    assert unpinned.display_order == 1
    east = distance_km(22.3, 114.2, 22.3, 114.3)
    north = distance_km(22.3, 114.2, 22.4, 114.2)
    assert north > east
    close = assign_in_district("Central and Western", 22.2814, 114.1580)
    assert close is not None and close.confident
    far = assign_in_district("Islands", 22.6, 114.6)
    assert far is not None and not far.confident


def test_create_location_rejects_a_district_that_has_neighbourhoods(
    db_session, sample_organization
) -> None:
    district = GeographicArea(name="Parent District", level="district", active=True)
    db_session.add(district)
    db_session.flush()
    db_session.add(
        GeographicArea(
            name="Child Neighbourhood",
            level="neighbourhood",
            parent_id=district.id,
            active=True,
        )
    )
    db_session.flush()
    repo = LocationRepository(db_session)
    with pytest.raises(ValidationError) as exc_info:
        _create_location(
            repo,
            {
                "org_id": str(sample_organization.id),
                "area_id": str(district.id),
                "address": "1 Parent Road",
            },
        )
    assert exc_info.value.field == "area_id"


def test_lookup_district_name_uses_the_pin(db_session) -> None:
    district = GeographicArea(name="Pin District", level="district", active=True)
    db_session.add(district)
    db_session.flush()
    near = GeographicArea(
        name="Near Side",
        level="neighbourhood",
        parent_id=district.id,
        active=True,
        lat=22.28,
        lng=114.18,
    )
    far = GeographicArea(
        name="Far Side",
        level="neighbourhood",
        parent_id=district.id,
        active=True,
        lat=22.4,
        lng=114.3,
    )
    db_session.add_all([near, far])
    db_session.flush()
    picked = lookup_district_area_id(db_session, "Pin District", 22.28, 114.18)
    assert picked == str(near.id)


def test_apply_snaps_a_district_proposal(db_session) -> None:
    org = Organization(name="Harbour Club", manager_id="manager-1")
    district = GeographicArea(name="Wan Chai", level="district", active=True)
    db_session.add_all([org, district])
    db_session.flush()
    for name in ("Wan Chai", "Causeway Bay"):
        db_session.add(
            GeographicArea(
                name=name,
                level="neighbourhood",
                parent_id=district.id,
                active=True,
            )
        )
    db_session.flush()
    proposal = LocationFixProposal(
        entity_type="organization",
        entity_id=org.id,
        org_id=org.id,
        kind="create_location",
        source="model",
        proposed_location={
            "address": "1 Causeway Road",
            "area_id": str(district.id),
            "lat": 22.2803,
            "lng": 114.1846,
        },
        status="pending",
    )
    db_session.add(proposal)
    db_session.flush()
    decide_proposal(db_session, proposal.id, "apply", "admin")
    location = db_session.scalars(
        select(Location).where(Location.org_id == org.id)
    ).one()
    area = db_session.get(GeographicArea, location.area_id)
    assert area is not None
    assert area.name == "Causeway Bay"


def test_lookup_prefers_the_neighbourhood_leaf(db_session) -> None:
    district = GeographicArea(name="Shared Name", level="district", active=True)
    db_session.add(district)
    db_session.flush()
    neighbourhood = GeographicArea(
        name="Shared Name",
        level="neighbourhood",
        parent_id=district.id,
        active=True,
    )
    db_session.add(neighbourhood)
    db_session.flush()
    assert lookup_district_area_id(db_session, "Shared Name") == str(neighbourhood.id)


def test_resolve_leaf_picks_the_nearest_child(db_session) -> None:
    district = GeographicArea(name="Wan Chai", level="district", active=True)
    db_session.add(district)
    db_session.flush()
    for name in ("Wan Chai", "Causeway Bay"):
        db_session.add(
            GeographicArea(
                name=name,
                level="neighbourhood",
                parent_id=district.id,
                active=True,
            )
        )
    db_session.flush()
    picked = resolve_leaf(db_session, district, 22.2803, 114.1846)
    assert picked is not None
    assert picked.name == "Causeway Bay"
