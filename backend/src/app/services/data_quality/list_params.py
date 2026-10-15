"""Shared list filters for data-quality proposal tables."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.exceptions import ValidationError


def choice(value: Any, allowed: frozenset[str], field: str) -> str | None:
    """Return a stripped allowed value, or None when the input is blank."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text not in allowed:
        raise ValidationError(f"Invalid {field}", field=field)
    return text


def optional_uuid(value: Any, field: str) -> UUID | None:
    if value in (None, ""):
        return None
    return parse_uuid(str(value), field)


def parse_uuid(value: str, field: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("id must be a UUID", field=field) from exc


def ilike_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def encode_cursor(created_at: datetime, proposal_id) -> str:
    raw = json.dumps({"t": created_at.isoformat(), "id": str(proposal_id)}).encode()
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, UUID]:
    padded = value + "=" * (-len(value) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))
        stamp = datetime.fromisoformat(str(payload["t"]))
        proposal_id = UUID(str(payload["id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("cursor is invalid", field="cursor") from exc
    return stamp, proposal_id
