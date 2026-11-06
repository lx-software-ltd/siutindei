"""Open, temporarily closed, or permanently closed on a location."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from app.api.admin_imports_export import serialize_export_location
from app.api.admin_imports_upsert import upsert_location
from app.api.admin_resource_location import (
    _create_location,
    _serialize_location,
    _update_location,
)
from app.api.search import map_row_to_result
from app.db.queries import ActivitySearchFilters, build_search_query
from app.db.repositories import LocationRepository
from app.exceptions import ValidationError
from app.services.catalog_version_payload import location_payload
from app.services.catalog_version_shape import location_shape, payload_differs
from app.services.location_fix_apply import _apply_update
from app.services.staging_search_store import _is_visible_listing


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
    kept = _update_location(repo, updated, {"address": sample_location.address})
    assert kept.status == "permanently_closed"
    assert kept.address == sample_location.address


def test_update_rejects_a_blank_status(db_session, sample_location) -> None:
    repo = LocationRepository(db_session)
    with pytest.raises(ValidationError) as exc_info:
        _update_location(repo, sample_location, {"status": ""})
    assert exc_info.value.field == "status"
    assert sample_location.status == "open"


def test_closed_location_rejects_detail_edits(db_session, sample_location) -> None:
    repo = LocationRepository(db_session)
    sample_location.address = "1 Status Road"
    sample_location.lat = Decimal("22.280000")
    sample_location.lng = Decimal("114.150000")
    _update_location(repo, sample_location, {"status": "temporarily_closed"})
    with pytest.raises(ValidationError) as exc_info:
        _update_location(repo, sample_location, {"address": "9 Status Road"})
    assert exc_info.value.field == "address"
    assert sample_location.address == "1 Status Road"
    with pytest.raises(ValidationError) as closed_with_edit:
        _update_location(
            repo,
            sample_location,
            {"status": "permanently_closed", "lat": Decimal("22.290000")},
        )
    assert closed_with_edit.value.field == "lat"
    assert sample_location.lat == Decimal("22.280000")
    opened = _update_location(
        repo,
        sample_location,
        {"status": "open", "address": "9 Status Road"},
    )
    assert opened.status == "open"
    assert opened.address == "9 Status Road"


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
    assert again.lat == Decimal("22.280000")


def test_import_create_stores_status_and_export_keeps_it(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    location, status = upsert_location(
        db_session,
        sample_organization,
        {
            "name": "Closed Hall",
            "area_id": str(sample_geographic_area.id),
            "status": "permanently_closed",
        },
        "Closed Hall",
    )
    assert status == "created"
    assert location.status == "permanently_closed"
    exported = serialize_export_location(location, {str(location.id): "Closed Hall"})
    assert exported["status"] == "permanently_closed"


def test_search_hides_a_permanently_closed_venue(
    db_session,
    sample_activity,
    sample_location,
    sample_pricing,
    sample_schedule,
) -> None:
    del sample_activity, sample_pricing, sample_schedule
    sample_location.status = "temporarily_closed"
    db_session.flush()
    rows = db_session.execute(build_search_query(ActivitySearchFilters(limit=10))).all()
    assert len(rows) == 1
    assert map_row_to_result(rows[0], {}).location.status == "temporarily_closed"

    sample_location.status = "permanently_closed"
    db_session.flush()
    hidden = db_session.execute(
        build_search_query(ActivitySearchFilters(limit=10))
    ).all()
    assert hidden == []
    assert (
        _is_visible_listing(
            {
                "organization": {"status": "operational"},
                "location": {"status": "permanently_closed"},
            }
        )
        is False
    )
    assert (
        _is_visible_listing(
            {
                "organization": {"status": "operational"},
                "location": {"status": "temporarily_closed"},
            }
        )
        is True
    )


def test_pin_fix_does_not_move_a_closed_location(db_session, sample_location) -> None:
    sample_location.status = "temporarily_closed"
    sample_location.address = "1 Status Road"
    sample_location.lat = Decimal("22.280000")
    sample_location.lng = Decimal("114.150000")
    db_session.flush()

    class _Row:
        entity_type = "location"
        target_location_id = None

        def __init__(self, entity_id) -> None:
            self.entity_id = entity_id
            self.proposed_location = {
                "address": "1 Status Road",
                "lat": 22.29,
                "lng": 114.15,
                "lookup": {"grade": "precise", "district_consistent": True},
            }

    with pytest.raises(ValidationError) as exc_info:
        _apply_update(
            db_session,
            _Row(sample_location.id),
            geocode=False,
            area_id=None,
        )
    assert exc_info.value.field == "status"
    assert sample_location.lat == Decimal("22.280000")


def test_serialized_coordinates_are_json_numbers(
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
            "address": "1 Pin Road",
            "lat": Decimal("22.278000"),
            "lng": Decimal("114.175000"),
        },
    )
    body = _serialize_location(location)
    assert body["lat"] == 22.278
    assert body["lng"] == 114.175
    assert isinstance(body["lat"], float)
    assert isinstance(body["lng"], float)
    encoded = json.loads(json.dumps(body, default=str))
    assert encoded["lat"] == 22.278
    assert encoded["lng"] == 114.175
    assert isinstance(encoded["lat"], float)
    assert isinstance(encoded["lng"], float)

    blank = _create_location(
        repo,
        {
            "org_id": str(sample_organization.id),
            "area_id": str(sample_geographic_area.id),
            "address": "2 Pin Road",
        },
    )
    assert _serialize_location(blank)["lat"] is None
    assert _serialize_location(blank)["lng"] is None


def test_status_is_not_an_import_difference() -> None:
    base = {"address": "1 Pier Road", "status": "open"}
    live = {**base, "status": "temporarily_closed"}
    assert "status" not in location_shape(live)
    assert payload_differs("location", live, base) is False
