"""Field helpers for admin import payloads."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from app.exceptions import ValidationError

FLAT_ORG_PASSTHROUGH_FIELDS = {
    "area_name",
    "category_name",
    "address",
    "lat",
    "lng",
    "website",
    "phone",
    "source_url",
    "vetting_note",
}

FLAT_ACTIVITY_DEFAULT_AGE_MIN = 0
FLAT_ACTIVITY_DEFAULT_AGE_MAX = 18


def apply_default_manager_id(payload: dict[str, Any]) -> None:
    """Copy root default_manager_id onto orgs that lack manager_id."""
    raw = payload.get("default_manager_id")
    if raw is None:
        return
    manager_id = _require_uuid(raw, "default_manager_id")
    orgs = payload.get("organizations")
    if not isinstance(orgs, list):
        return
    for org in orgs:
        if not isinstance(org, dict):
            continue
        existing = org.get("manager_id")
        if existing is None or str(existing).strip() == "":
            org["manager_id"] = manager_id


def apply_source_attribution(record: dict[str, Any]) -> None:
    """Append 'Source: <url> — <note>' when either field is present."""
    url_text = _optional_text(record.get("source_url"))
    note_text = _optional_text(record.get("vetting_note"))
    if not url_text and not note_text:
        return
    line = f"Source: {url_text} — {note_text}"
    description = _optional_text(record.get("description"))
    record["description"] = f"{description}\n{line}" if description else line


def expand_board_flat_org(raw_org: dict[str, Any]) -> None:
    """Turn a board catalog org into nested location + activity rows.

    Board catalog JSON is flat: area_name / category_name / address live on
    the organization. Nested locations/activities are left alone when present.
    """
    apply_flat_org_contacts(raw_org)
    locations = raw_org.get("locations")
    has_locations = isinstance(locations, list) and bool(locations)
    if not has_locations and _has_flat_location_fields(raw_org):
        raw_org["locations"] = [_location_from_flat_org(raw_org)]

    activities = raw_org.get("activities")
    has_activities = isinstance(activities, list) and bool(activities)
    if not has_activities and _has_flat_activity_fields(raw_org):
        raw_org["activities"] = [_activity_from_flat_org(raw_org)]


def apply_flat_org_contacts(raw_org: dict[str, Any]) -> None:
    """Map a board `phone` string onto phone_country_code / phone_number."""
    if raw_org.get("phone_number"):
        return
    raw_phone = raw_org.get("phone")
    if raw_phone is None:
        return
    digits = re.sub(r"\D", "", str(raw_phone))
    if digits.startswith("852") and len(digits) == 11:
        digits = digits[3:]
    if len(digits) == 8:
        raw_org.setdefault("phone_country_code", "HK")
        raw_org["phone_number"] = digits


def _has_flat_location_fields(raw_org: dict[str, Any]) -> bool:
    return any(
        raw_org.get(key) not in (None, "")
        for key in ("area_name", "area_id", "address", "lat", "lng")
    )


def _has_flat_activity_fields(raw_org: dict[str, Any]) -> bool:
    return raw_org.get("category_name") not in (None, "") or raw_org.get(
        "category_id"
    ) not in (None, "")


def _location_from_flat_org(raw_org: dict[str, Any]) -> dict[str, Any]:
    address = _optional_text(raw_org.get("address")) or _optional_text(
        raw_org.get("name")
    )
    location: dict[str, Any] = {"name": address, "address": address}
    if raw_org.get("area_id") not in (None, ""):
        location["area_id"] = raw_org["area_id"]
    if raw_org.get("area_name") not in (None, ""):
        location["area_name"] = raw_org["area_name"]
    if raw_org.get("lat") is not None:
        location["lat"] = raw_org["lat"]
    if raw_org.get("lng") is not None:
        location["lng"] = raw_org["lng"]
    return location


def _activity_from_flat_org(raw_org: dict[str, Any]) -> dict[str, Any]:
    activity: dict[str, Any] = {
        "name": raw_org.get("name"),
        "age_min": FLAT_ACTIVITY_DEFAULT_AGE_MIN,
        "age_max": FLAT_ACTIVITY_DEFAULT_AGE_MAX,
    }
    if raw_org.get("description") not in (None, ""):
        activity["description"] = raw_org["description"]
    if raw_org.get("category_id") not in (None, ""):
        activity["category_id"] = raw_org["category_id"]
    if raw_org.get("category_name") not in (None, ""):
        activity["category_name"] = raw_org["category_name"]
    if raw_org.get("source_url") not in (None, ""):
        activity["source_url"] = raw_org["source_url"]
    if raw_org.get("vetting_note") not in (None, ""):
        activity["vetting_note"] = raw_org["vetting_note"]
    return activity


def _require_uuid(value: Any, field: str) -> str:
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    try:
        return str(UUID(value))
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            f"{field} must be a UUID",
            field=field,
        ) from exc


def _optional_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
