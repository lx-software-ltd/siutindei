"""Open, temporarily closed, or permanently closed on a location."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.api.admin_imports_upsert import upsert_location
from app.api.admin_resource_location import (
    _create_location,
    _serialize_location,
    _update_location,
)
from app.db.repositories import LocationRepository
from app.exceptions import ValidationError
from app.services.catalog_version_payload import location_payload
from app.services.catalog_version_shape import location_shape, payload_differs


def test_create_defaults_to_open(
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
            "address": "1 Status Road",
        },
    )
    db_session.add(location)
    db_session.flush()
    assert location.status == "open"
    assert _serialize_location(location)["status"] == "open"
    assert location_payload(location)["status"] == "open"


def test_create_stores_a_closed_status(
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
            "address": "1 Status Road",
            "status": " temporarily_closed ",
        },
    )
    assert location.status == "temporarily_closed"


def test_invalid_status_is_rejected(
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
                "address": "1 Status Road",
                "status": "hidden",
            },
        )
    assert exc_info.value.field == "status"


def test_update_changes_status(db_session, sample_location) -> None:
    repo = LocationRepository(db_session)
    assert sample_location.status == "open"
    updated = _update_location(
        repo,
        sample_location,
        {"status": "permanently_closed"},
    )
    assert updated.status == "permanently_closed"
    kept = _update_location(repo, updated, {"address": "9 Status Road"})
    assert kept.status == "permanently_closed"


def test_update_rejects_a_blank_status(db_session, sample_location) -> None:
    repo = LocationRepository(db_session)
    with pytest.raises(ValidationError) as exc_info:
        _update_location(repo, sample_location, {"status": ""})
    assert exc_info.value.field == "status"
    assert sample_location.status == "open"


def test_import_creates_open_and_keeps_a_later_closure(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    location, status = upsert_location(
        db_session,
        sample_organization,
        {
            "name": "Status Hall",
            "area_id": str(sample_geographic_area.id),
            "lat": Decimal("22.280000"),
            "lng": Decimal("114.150000"),
            "status": "permanently_closed",
        },
        "Status Hall",
    )
    assert status == "created"
    assert location.status == "open"

    repo = LocationRepository(db_session)
    _update_location(repo, location, {"status": "temporarily_closed"})
    db_session.flush()

    again, status = upsert_location(
        db_session,
        sample_organization,
        {
            "name": "Status Hall",
            "address": "Status Hall",
            "area_id": str(sample_geographic_area.id),
            "lat": Decimal("22.290000"),
            "lng": Decimal("114.150000"),
            "status": "open",
        },
        "Status Hall",
    )
    assert status == "updated"
    assert again.status == "temporarily_closed"
    assert again.lat == Decimal("22.290000")


def test_status_is_not_an_import_difference() -> None:
    base = {"address": "1 Pier Road", "status": "open"}
    live = {**base, "status": "temporarily_closed"}
    assert "status" not in location_shape(live)
    assert payload_differs("location", live, base) is False
