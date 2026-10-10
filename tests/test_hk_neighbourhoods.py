"""Hong Kong neighbourhood catalog and leaf location areas."""

from __future__ import annotations

import pytest
from app.api.admin_imports_lookups import lookup_district_area_id
from app.api.admin_resource_location import _create_location
from app.data.hk_neighbourhoods import HK_DISTRICTS, NEIGHBOURHOODS, nearest_in_district
from app.db.models import GeographicArea
from app.db.repositories import LocationRepository
from app.exceptions import ValidationError
from app.services.area_assignment import resolve_leaf


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
