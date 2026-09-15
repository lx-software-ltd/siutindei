"""Tests for admin import helpers."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.admin_imports_upsert import (
    _apply_import_activity_category,
    _apply_import_location_area,
)
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


def _session_returning_scalar(value: object) -> MagicMock:
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = value
    return session


def test_import_location_resolves_area_name() -> None:
    area_id = uuid4()
    session = _session_returning_scalar(area_id)
    raw = {"area_name": "Central and Western"}
    body = dict(raw)
    _apply_import_location_area(session, raw, body)
    assert body["area_id"] == str(area_id)
    assert "area_name" not in body
    session.execute.assert_called_once()


def test_import_location_unknown_area_name() -> None:
    session = _session_returning_scalar(None)
    raw = {"area_name": "No Such District"}
    body = dict(raw)
    with pytest.raises(ValidationError) as exc_info:
        _apply_import_location_area(session, raw, body)
    assert exc_info.value.message == "unknown area_name"
    assert exc_info.value.field == "area_name"


def test_import_location_area_id_wins_over_area_name() -> None:
    session = MagicMock()
    area_id = uuid4()
    raw = {
        "area_id": str(area_id),
        "area_name": "Wrong District Name",
    }
    body = dict(raw)
    _apply_import_location_area(session, raw, body)
    assert body["area_id"] == str(area_id)
    assert "area_name" not in body
    session.execute.assert_not_called()


def test_import_activity_resolves_category_name() -> None:
    category_id = uuid4()
    session = _session_returning_scalar(category_id)
    raw = {"category_name": "Sport"}
    body = dict(raw)
    _apply_import_activity_category(session, raw, body)
    assert body["category_id"] == str(category_id)
    assert "category_name" not in body
    session.execute.assert_called_once()


def test_import_activity_unknown_category_name() -> None:
    session = _session_returning_scalar(None)
    raw = {"category_name": "No Such Category"}
    body = dict(raw)
    with pytest.raises(ValidationError) as exc_info:
        _apply_import_activity_category(session, raw, body)
    assert exc_info.value.message == "unknown category_name"
    assert exc_info.value.field == "category_name"


def test_import_activity_category_id_wins_over_category_name() -> None:
    session = MagicMock()
    category_id = uuid4()
    raw = {
        "category_id": str(category_id),
        "category_name": "Other Category",
    }
    body = dict(raw)
    _apply_import_activity_category(session, raw, body)
    assert body["category_id"] == str(category_id)
    assert "category_name" not in body
    session.execute.assert_not_called()
