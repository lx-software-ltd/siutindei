"""Tests for admin import helpers."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.api.admin_imports_upsert import upsert_activity, upsert_location
from app.api.admin_imports_utils import (
    from_utc_weekly,
    parse_time_minutes,
    parse_timezone,
    to_utc_weekly,
)
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
) -> None:
    from app.db.models import GeographicArea

    area = GeographicArea(
        name="Import District Resolve",
        level="district",
        active=True,
    )
    db_session.add(area)
    db_session.flush()

    location, status = upsert_location(
        db_session,
        sample_organization,
        _location_payload(area_name="Import District Resolve"),
        "Import Loc Resolve",
    )
    assert status == "created"
    assert str(location.area_id) == str(area.id)


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
) -> None:
    from app.db.models import ActivityCategory

    category = ActivityCategory(
        name="Import Category Resolve",
        display_order=99,
    )
    db_session.add(category)
    db_session.flush()

    activity, status = upsert_activity(
        db_session,
        sample_organization,
        _activity_payload(category_name="Import Category Resolve"),
    )
    assert status == "created"
    assert str(activity.category_id) == str(category.id)


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
