"""Tests for search cursor encoding."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from app.api.search_page import decode_cursor as _decode_cursor
from app.api.search_page import encode_cursor as _encode_cursor
from app.api.search_page import parse_cursor as _parse_cursor
from app.exceptions import CursorError


def test_encode_decode_cursor_roundtrip() -> None:
    """Ensure cursor roundtrips to the same schedule id."""

    schedule_id = uuid4()
    cursor = _encode_cursor(2, 480, schedule_id)
    payload = _decode_cursor(cursor)
    assert payload["schedule_id"] == str(schedule_id)
    assert payload["day_of_week_utc"] == 2
    assert payload["start_minutes_utc"] == 480


def test_parse_cursor_returns_uuid() -> None:
    """Ensure the cursor parser returns a UUID."""

    schedule_id = uuid4()
    cursor = _encode_cursor(2, 480, schedule_id)
    parsed = _parse_cursor(cursor)
    assert parsed is not None
    assert parsed.schedule_id == schedule_id
    assert parsed.day_of_week_utc == 2
    assert parsed.start_minutes_utc == 480


def test_parse_cursor_rejects_invalid_value() -> None:
    """Ensure invalid cursors raise a CursorError."""

    raw = json.dumps({"schedule_id": "not-a-uuid"}).encode("utf-8")
    cursor = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    with pytest.raises(CursorError):
        _parse_cursor(cursor)
