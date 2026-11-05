"""Optional venue label on a location."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.api.admin_imports_upsert import upsert_location
from app.api.admin_resource_location import (
    _create_location,
    _serialize_location,
    _update_location,
)
from app.db.models import CatalogVersion, ImportSettings
from app.db.repositories import LocationRepository
from app.exceptions import ValidationError
from app.services.catalog_version_match import (
    ADMIN_EDITS_OVERWRITTEN,
    IMPORT_EDITS_OVERWRITTEN,
    MIXED_EDITS_OVERWRITTEN,
    SYSTEM_EDITS_OVERWRITTEN,
)
from app.services.catalog_version_payload import location_payload
from app.services.import_merge import jsonable
from sqlalchemy import select, text


def test_create_location_stores_a_trimmed_name(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    repo = LocationRepository(db_session)
    location = _create_location(
        repo,
        {
            "org_id": str(sample_organization.id),
            "area_id": str(sample_geographic_area.id),
            "address": "1 Name Road",
            "name": "  Harbour Hall  ",
        },
    )
    db_session.add(location)
    db_session.flush()
    assert location.name == "Harbour Hall"
    assert _serialize_location(location)["name"] == "Harbour Hall"
    assert location_payload(location)["name"] == "Harbour Hall"


def test_blank_name_is_stored_as_null(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    repo = LocationRepository(db_session)
    location = _create_location(
        repo,
        {
            "org_id": str(sample_organization.id),
            "area_id": str(sample_geographic_area.id),
            "address": "1 Name Road",
            "name": "   ",
        },
    )
    assert location.name is None
    assert _serialize_location(location)["name"] is None


def test_name_longer_than_200_is_rejected(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    repo = LocationRepository(db_session)
    with pytest.raises(ValidationError) as exc_info:
        _create_location(
            repo,
            {
                "org_id": str(sample_organization.id),
                "area_id": str(sample_geographic_area.id),
                "address": "1 Name Road",
                "name": "x" * 201,
            },
        )
    assert exc_info.value.field == "name"


def test_update_clears_the_name(db_session, sample_location) -> None:
    repo = LocationRepository(db_session)
    named = _update_location(repo, sample_location, {"name": "Harbour Hall"})
    assert named.name == "Harbour Hall"
    cleared = _update_location(repo, named, {"name": ""})
    assert cleared.name is None


def test_two_venues_may_share_a_name(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    repo = LocationRepository(db_session)
    shared = {
        "org_id": str(sample_organization.id),
        "area_id": str(sample_geographic_area.id),
        "name": "Harbour Hall",
    }
    first = _create_location(repo, {**shared, "address": "1 Name Road"})
    second = _create_location(repo, {**shared, "address": "2 Name Road"})
    db_session.add(first)
    db_session.add(second)
    db_session.flush()
    assert first.name == second.name


def test_import_name_stays_the_address(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    location, status = upsert_location(
        db_session,
        sample_organization,
        {
            "name": "Studio Hall",
            "area_id": str(sample_geographic_area.id),
            "lat": Decimal("22.280000"),
            "lng": Decimal("114.150000"),
        },
        "Studio Hall",
    )
    assert status == "created"
    assert location.address == "Studio Hall"
    assert location.name is None


def test_import_keeps_an_admin_label(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    location, _status = upsert_location(
        db_session,
        sample_organization,
        {
            "name": "Studio Hall",
            "area_id": str(sample_geographic_area.id),
            "lat": Decimal("22.280000"),
            "lng": Decimal("114.150000"),
        },
        "Studio Hall",
    )
    repo = LocationRepository(db_session)
    _update_location(repo, location, {"name": "Main Hall"})
    db_session.flush()

    again, status = upsert_location(
        db_session,
        sample_organization,
        {
            "name": "Studio Hall",
            "address": "Studio Hall",
            "area_id": str(sample_geographic_area.id),
            "lat": Decimal("22.290000"),
            "lng": Decimal("114.150000"),
        },
        "Studio Hall",
    )
    assert status == "updated"
    assert again.name == "Main Hall"
    assert again.lat == Decimal("22.290000")


def test_reimport_does_not_warn_that_the_label_was_overwritten(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    _apply_mode(db_session)
    location, _status = upsert_location(
        db_session,
        sample_organization,
        {
            "name": "Studio Hall",
            "area_id": str(sample_geographic_area.id),
            "lat": Decimal("22.280000"),
            "lng": Decimal("114.150000"),
        },
        "Studio Hall",
    )
    version1 = db_session.scalars(
        select(CatalogVersion).where(
            CatalogVersion.entity_type == "location",
            CatalogVersion.entity_id == location.id,
            CatalogVersion.version == 1,
        )
    ).first()
    if version1 is None:
        version1 = CatalogVersion(
            entity_type="location",
            entity_id=location.id,
            org_id=sample_organization.id,
            version=1,
            action="created",
            snapshot=jsonable(location_payload(location)),
            txid=1,
        )
        db_session.add(version1)
        db_session.flush()
    assert version1.snapshot.get("name") in (None, "")
    if db_session.get_bind().dialect.name == "postgresql":
        db_session.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": "admin-sub"},
        )
    location.name = "Main Hall"
    db_session.flush()

    warnings: list[str] = []
    again, status = upsert_location(
        db_session,
        sample_organization,
        {
            "name": "Studio Hall",
            "address": "Studio Hall",
            "area_id": str(sample_geographic_area.id),
            "lat": Decimal("22.290000"),
            "lng": Decimal("114.150000"),
        },
        "Studio Hall",
        warnings=warnings,
    )
    assert status == "updated"
    assert again.name == "Main Hall"
    assert again.lat == Decimal("22.290000")
    overwritten = {
        ADMIN_EDITS_OVERWRITTEN,
        IMPORT_EDITS_OVERWRITTEN,
        MIXED_EDITS_OVERWRITTEN,
        SYSTEM_EDITS_OVERWRITTEN,
    }
    assert overwritten.isdisjoint(warnings)


def _apply_mode(session) -> None:
    row = session.get(ImportSettings, 1)
    if row is None:
        row = ImportSettings(id=1, existing_rows="apply")
        session.add(row)
    else:
        row.existing_rows = "apply"
    session.flush()
