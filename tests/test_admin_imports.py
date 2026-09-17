"""Tests for admin import helpers."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_imports import _parse_dry_run
from app.api.admin_imports_fields import (
    apply_source_attribution,
    collect_flat_org_warnings,
)
from app.api.admin_imports_importer import process_import_payload
from app.api.admin_imports_upsert import upsert_activity, upsert_location
from app.api.admin_imports_utils import (
    from_utc_weekly,
    parse_time_minutes,
    parse_timezone,
    to_utc_weekly,
)
from app.db.models import Activity, Location, Organization
from app.exceptions import ValidationError


def test_parse_time_minutes_accepts_hhmm() -> None:
    assert parse_time_minutes("09:30", "start_time") == 9 * 60 + 30


def test_parse_time_minutes_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        parse_time_minutes("25:00", "start_time")


def test_timezone_validation_requires_iana() -> None:
    with pytest.raises(ValidationError):
        parse_timezone("Not/A_Timezone", "timezone")


def test_utc_round_trip_preserves_weekly_entry() -> None:
    tz = parse_timezone("UTC", "timezone")
    day_utc, start_utc, end_utc = to_utc_weekly(1, 9 * 60, 10 * 60, tz)
    local_day, local_start, local_end = from_utc_weekly(
        day_utc,
        start_utc,
        end_utc,
        tz,
    )
    assert local_day == 1
    assert local_start == 9 * 60
    assert local_end == 10 * 60


def _location_payload(**overrides: object) -> dict:
    payload = {
        "lat": Decimal("22.282667"),
        "lng": Decimal("114.158167"),
    }
    payload.update(overrides)
    return payload


def _activity_payload(**overrides: object) -> dict:
    payload = {
        "name": "Import Activity",
        "description": "Desc",
        "age_min": 5,
        "age_max": 12,
    }
    payload.update(overrides)
    return payload


def test_upsert_location_resolves_area_name(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    location, status = upsert_location(
        db_session,
        sample_organization,
        _location_payload(area_name=sample_geographic_area.name),
        "Import Loc Resolve",
    )
    assert status == "created"
    assert str(location.area_id) == str(sample_geographic_area.id)


def test_upsert_location_unknown_area_name(
    db_session,
    sample_organization,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        upsert_location(
            db_session,
            sample_organization,
            _location_payload(area_name="Missing District"),
            "Import Loc Unknown",
        )
    assert exc_info.value.field == "area_name"
    assert exc_info.value.message == "unknown area_name"


def test_upsert_location_area_id_wins_over_area_name(
    db_session,
    sample_organization,
    sample_geographic_area,
) -> None:
    from app.db.models import GeographicArea

    other = GeographicArea(
        name="Other District",
        level="district",
        active=True,
    )
    db_session.add(other)
    db_session.flush()

    location, _status = upsert_location(
        db_session,
        sample_organization,
        _location_payload(
            area_id=str(sample_geographic_area.id),
            area_name="Other District",
        ),
        "Import Loc Both",
    )
    assert str(location.area_id) == str(sample_geographic_area.id)


def test_upsert_activity_resolves_category_name(
    db_session,
    sample_organization,
    sample_activity_category,
) -> None:
    activity, status = upsert_activity(
        db_session,
        sample_organization,
        _activity_payload(category_name=sample_activity_category.name),
    )
    assert status == "created"
    assert str(activity.category_id) == str(sample_activity_category.id)


def test_upsert_activity_unknown_category_name(
    db_session,
    sample_organization,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        upsert_activity(
            db_session,
            sample_organization,
            _activity_payload(category_name="Missing Category"),
        )
    assert exc_info.value.field == "category_name"
    assert exc_info.value.message == "unknown category_name"


def test_upsert_activity_category_id_wins_over_category_name(
    db_session,
    sample_organization,
    sample_activity_category,
) -> None:
    from app.db.models import ActivityCategory

    other = ActivityCategory(name="Other Category", display_order=1)
    db_session.add(other)
    db_session.flush()

    activity, _status = upsert_activity(
        db_session,
        sample_organization,
        _activity_payload(
            category_id=str(sample_activity_category.id),
            category_name="Other Category",
            name="Import Activity Both",
        ),
    )
    assert str(activity.category_id) == str(sample_activity_category.id)


def test_apply_source_attribution_appends_line() -> None:
    record = {
        "description": "Hello",
        "source_url": "https://example.test",
        "vetting_note": "checked",
    }
    apply_source_attribution(record)
    assert record["description"] == ("Hello\nSource: https://example.test — checked")


def test_apply_source_attribution_skips_when_both_empty() -> None:
    record = {"description": "Hello", "source_url": "", "vetting_note": "  "}
    apply_source_attribution(record)
    assert record["description"] == "Hello"


def test_apply_source_attribution_url_only() -> None:
    record = {"description": "Hello", "source_url": "https://example.test"}
    apply_source_attribution(record)
    assert record["description"] == "Hello\nSource: https://example.test"


def test_apply_source_attribution_note_only() -> None:
    record = {"description": "Hello", "vetting_note": "checked"}
    apply_source_attribution(record)
    assert record["description"] == "Hello\nSource: checked"


def test_collect_flat_org_warnings_for_nested_and_website() -> None:
    warnings: list[str] = []
    collect_flat_org_warnings(
        {
            "address": "1 Park Road",
            "area_name": "Wan Chai",
            "category_name": "Playground",
            "website": "https://park.test",
            "locations": [{"name": "Nested Loc"}],
            "activities": [{"name": "Nested Act"}],
        },
        "organizations[0]",
        warnings,
    )
    assert any("ignored flat location fields" in item for item in warnings)
    assert any("ignored flat activity fields" in item for item in warnings)
    assert any("website is accepted but not stored" in item for item in warnings)


def test_default_manager_id_fills_missing_manager(db_session) -> None:
    payload = {
        "default_manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "organizations": [{"name": "Default Manager Org"}],
    }
    summary, results = process_import_payload(db_session, payload, [])
    assert results[0]["status"] == "created"
    org = db_session.execute(
        select(Organization).where(Organization.name == "Default Manager Org")
    ).scalar_one()
    assert str(org.manager_id) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert summary["organizations"]["created"] == 1


def test_default_manager_id_does_not_override_existing(db_session) -> None:
    payload = {
        "default_manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "organizations": [
            {
                "name": "Keeps Own Manager",
                "manager_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            }
        ],
    }
    _summary, results = process_import_payload(db_session, payload, [])
    assert results[0]["status"] == "created"
    org = db_session.execute(
        select(Organization).where(Organization.name == "Keeps Own Manager")
    ).scalar_one()
    assert str(org.manager_id) == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_default_manager_id_rejects_invalid_uuid(db_session) -> None:
    with pytest.raises(ValidationError) as exc_info:
        process_import_payload(
            db_session,
            {
                "default_manager_id": "not-a-uuid",
                "organizations": [],
            },
            [],
        )
    assert exc_info.value.field == "default_manager_id"


def test_source_fields_appended_on_org_and_activity(
    db_session,
    sample_activity_category,
    sample_geographic_area,
) -> None:
    payload = {
        "organizations": [
            {
                "name": "Source Org",
                "description": "Hello",
                "manager_id": "00000000-0000-0000-0000-000000000099",
                "source_url": "https://org.test",
                "vetting_note": "org-note",
                "locations": [
                    {
                        "name": "Source Loc",
                        "area_name": sample_geographic_area.name,
                        "lat": 22.2,
                        "lng": 114.1,
                    }
                ],
                "activities": [
                    {
                        "name": "Source Act",
                        "description": "Class",
                        "category_name": sample_activity_category.name,
                        "age_min": 5,
                        "age_max": 10,
                        "source_url": "https://act.test",
                        "vetting_note": "act-note",
                    }
                ],
            }
        ]
    }
    _summary, results = process_import_payload(db_session, payload, [])
    statuses = {item["type"]: item["status"] for item in results}
    assert statuses["organizations"] == "created"
    assert statuses["activities"] == "created"
    org = db_session.execute(
        select(Organization).where(Organization.name == "Source Org")
    ).scalar_one()
    assert org.description == "Hello\nSource: https://org.test — org-note"
    activity = db_session.execute(
        select(Activity).where(Activity.name == "Source Act")
    ).scalar_one()
    assert activity.description == "Class\nSource: https://act.test — act-note"


def test_board_flat_org_creates_location_and_activity(
    db_session,
    sample_activity_category,
    sample_geographic_area,
) -> None:
    payload = {
        "organizations": [
            {
                "name": "Flat Playground",
                "description": "A park",
                "manager_id": "00000000-0000-0000-0000-000000000088",
                "area_name": sample_geographic_area.name,
                "category_name": sample_activity_category.name,
                "address": "1 Park Road",
                "lat": 22.3,
                "lng": 114.2,
                "phone": "23456789",
                "source_url": "https://park.test",
                "vetting_note": "verified",
            }
        ]
    }
    warnings: list[str] = []
    _summary, results = process_import_payload(db_session, payload, warnings)
    assert not any("unknown fields" in item for item in warnings)
    by_type = {item["type"]: item for item in results}
    assert by_type["organizations"]["status"] == "created"
    assert by_type["locations"]["status"] == "created"
    assert by_type["activities"]["status"] == "created"

    org = db_session.execute(
        select(Organization).where(Organization.name == "Flat Playground")
    ).scalar_one()
    assert org.phone_country_code == "HK"
    assert org.phone_number == "23456789"
    assert org.description == "A park\nSource: https://park.test — verified"

    location = db_session.execute(
        select(Location).where(Location.org_id == org.id)
    ).scalar_one()
    assert location.address == "1 Park Road"
    assert str(location.area_id) == str(sample_geographic_area.id)

    activity = db_session.execute(
        select(Activity).where(Activity.org_id == org.id)
    ).scalar_one()
    assert activity.name == "Flat Playground"
    assert str(activity.category_id) == str(sample_activity_category.id)
    assert activity.age_range.lower == 0
    assert activity.age_range.upper >= 18
    assert activity.description == ("A park\nSource: https://park.test — verified")


def test_parse_dry_run_defaults_false() -> None:
    assert _parse_dry_run({}) is False
    assert _parse_dry_run({"dry_run": None}) is False
    assert _parse_dry_run({"dry_run": True}) is True


def test_parse_dry_run_rejects_non_bool() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _parse_dry_run({"dry_run": "true"})
    assert exc_info.value.field == "dry_run"


def test_dry_run_reports_created_without_persisting(test_engine) -> None:
    org_name = f"Dry Run Org {uuid4()}"
    payload = {
        "organizations": [
            {
                "name": org_name,
                "manager_id": "00000000-0000-0000-0000-000000000077",
            }
        ]
    }
    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            payload,
            [],
            dry_run=True,
        )
        session.rollback()
    assert results[0]["status"] == "created"
    assert results[0]["type"] == "organizations"
    with Session(test_engine) as session:
        found = session.execute(
            select(Organization).where(Organization.name == org_name)
        ).scalar_one_or_none()
    assert found is None


def test_live_import_persists_organization(test_engine) -> None:
    org_name = f"Live Import Org {uuid4()}"
    payload = {
        "organizations": [
            {
                "name": org_name,
                "manager_id": "00000000-0000-0000-0000-000000000076",
            }
        ]
    }
    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            payload,
            [],
            dry_run=False,
        )
    assert results[0]["status"] == "created"
    with Session(test_engine) as session:
        found = session.execute(
            select(Organization).where(Organization.name == org_name)
        ).scalar_one()
        assert str(found.manager_id) == "00000000-0000-0000-0000-000000000076"


def test_dry_run_child_failure_keeps_sibling_results(
    db_session,
    test_engine,
    sample_activity_category,
) -> None:
    org_name = f"Partial Dry {uuid4()}"
    payload = {
        "organizations": [
            {
                "name": org_name,
                "manager_id": "00000000-0000-0000-0000-000000000055",
                "locations": [
                    {
                        "name": "Bad Loc",
                        "area_name": "DOES-NOT-EXIST-DISTRICT",
                        "lat": 22.2,
                        "lng": 114.1,
                    }
                ],
                "activities": [
                    {
                        "name": "Good Act",
                        "category_id": str(sample_activity_category.id),
                        "age_min": 5,
                        "age_max": 10,
                    }
                ],
            }
        ]
    }
    _summary, results = process_import_payload(
        db_session,
        payload,
        [],
        dry_run=True,
    )
    by_type = {item["type"]: item for item in results}
    assert by_type["organizations"]["status"] == "created"
    assert by_type["locations"]["status"] == "failed"
    assert by_type["activities"]["status"] == "created"
    with Session(test_engine) as session:
        found = session.execute(
            select(Organization).where(Organization.name == org_name)
        ).scalar_one_or_none()
    assert found is None
