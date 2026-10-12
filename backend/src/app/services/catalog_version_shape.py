"""Compare shapes for catalog version 1.

The trigger stores the raw row. Import comparison normalises both the
file and that snapshot here, so timezone, money, and age rules live in
one place.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from app.api.admin_imports_catalog import normalize_org_name
from app.db.age_bounds import inclusive_age_bounds

ORG_SHAPE_KEYS = (
    "name",
    "description",
    "name_translations",
    "description_translations",
    "phone_country_code",
    "phone_number",
    "email",
    "whatsapp",
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "xiaohongshu",
    "wechat",
    "media_urls",
    "logo_media_url",
    "place_id",
    "status",
    "source",
    "source_id",
    "source_url",
    "source_note",
    "description_source",
)
ACTIVITY_SHAPE_KEYS = (
    "name",
    "description",
    "name_translations",
    "description_translations",
    "age_min",
    "age_max",
    "source_url",
    "source_note",
    "source_category_name",
)
LOCATION_SHAPE_KEYS = ("address", "area_id", "lat", "lng", "place_id")
PRICING_SHAPE_KEYS = (
    "location_address",
    "pricing_type",
    "amount",
    "currency",
    "sessions_count",
    "free_trial_class_offered",
)
SCHEDULE_SHAPE_KEYS = ("location_address", "languages", "entries")


def build_shape(entity_type: str, data: Mapping[str, Any]) -> dict[str, Any]:
    """Return the normalised compare shape for one entity."""
    if entity_type == "organization":
        return organization_shape(data)
    if entity_type == "activity":
        return activity_shape(data)
    if entity_type == "location":
        return location_shape(data)
    if entity_type == "pricing":
        return pricing_shape(data)
    if entity_type == "schedule":
        return schedule_shape(data)
    if entity_type == "media":
        return media_shape(data)
    return {}


def file_matches_snapshot(
    entity_type: str,
    incoming: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    present: set[str],
    *,
    partial: bool = False,
) -> bool:
    """True when the file's provided fields match the snapshot.

    Omitted file fields keep the snapshot value, so a file that does not
    mention a column is not a change. A partial snapshot (a merge record)
    compares only keys that snapshot actually stored.
    """
    baseline = build_shape(entity_type, snapshot)
    overlaid = dict(snapshot)
    for key in present:
        if key in incoming:
            overlaid[key] = incoming[key]
    if "age_min" in present or "age_max" in present:
        overlaid.pop("age_range", None)
    if "weekly_entries" in present or "entries" in present:
        entries = incoming.get("weekly_entries", incoming.get("entries"))
        overlaid["entries"] = entries
    candidate = build_shape(entity_type, overlaid)
    if not partial:
        return candidate == baseline
    keys = _snapshot_shape_keys(entity_type, snapshot)
    return all(candidate.get(key) == baseline.get(key) for key in keys)


def payload_differs(
    entity_type: str,
    current: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    partial: bool = False,
) -> bool:
    """True when the live row is not the version-1 snapshot."""
    baseline = build_shape(entity_type, snapshot)
    live = build_shape(entity_type, current)
    if not partial:
        return live != baseline
    keys = _snapshot_shape_keys(entity_type, snapshot)
    return any(live.get(key) != baseline.get(key) for key in keys)


def organization_shape(data: Mapping[str, Any]) -> dict[str, Any]:
    """Organisation fields an import is allowed to compare."""
    return {key: _org_value(key, data) for key in ORG_SHAPE_KEYS}


def activity_shape(data: Mapping[str, Any]) -> dict[str, Any]:
    """Activity fields. Category id is a taxonomy choice, not source data."""
    age_min, age_max = _ages(data)
    return {
        "name": _norm_name(data.get("name")),
        "description": _text(data.get("description")),
        "name_translations": _translations(data.get("name_translations")),
        "description_translations": _translations(data.get("description_translations")),
        "age_min": age_min,
        "age_max": age_max,
        "source_url": _text(data.get("source_url")),
        "source_note": _text(data.get("source_note")),
        "source_category_name": _text(data.get("source_category_name")),
    }


def location_shape(data: Mapping[str, Any]) -> dict[str, Any]:
    """Location identity: address, area, pin, and place id."""
    return {
        "address": _norm_name(data.get("address")),
        "area_id": _text(data.get("area_id")),
        "lat": _quantize(data.get("lat"), 6),
        "lng": _quantize(data.get("lng"), 6),
        "place_id": _text(data.get("place_id")),
    }


def pricing_shape(data: Mapping[str, Any]) -> dict[str, Any]:
    """Pricing identity includes the venue address and the price itself."""
    pricing_type = data.get("pricing_type")
    if hasattr(pricing_type, "value"):
        pricing_type = pricing_type.value
    return {
        "location_address": _norm_name(data.get("location_address")),
        "pricing_type": _text(pricing_type),
        "amount": _quantize(data.get("amount"), 2),
        "currency": _text(data.get("currency")),
        "sessions_count": _int(data.get("sessions_count")),
        "free_trial_class_offered": _bool(data.get("free_trial_class_offered")),
    }


def schedule_shape(data: Mapping[str, Any]) -> dict[str, Any]:
    """Schedule identity is the venue, languages, and UTC slots."""
    return {
        "location_address": _norm_name(data.get("location_address")),
        "languages": _strings(data.get("languages")),
        "entries": _entries(data),
    }


def media_shape(data: Mapping[str, Any]) -> dict[str, Any]:
    """Media is the ordered URL list and the logo."""
    return {
        "media_urls": _urls(data.get("media_urls")),
        "logo_media_url": _text(data.get("logo_media_url")),
    }


def _org_value(key: str, data: Mapping[str, Any]) -> Any:
    if key == "name":
        return _norm_name(data.get("name"))
    if key in {"name_translations", "description_translations"}:
        return _translations(data.get(key))
    if key == "media_urls":
        return _urls(data.get(key))
    return _text(data.get(key))


def _snapshot_shape_keys(entity_type: str, snapshot: Mapping[str, Any]) -> set[str]:
    shape = build_shape(entity_type, snapshot)
    stored = set(snapshot)
    if "age_range" in stored:
        stored.update({"age_min", "age_max"})
    if "entries" in stored or "weekly_entries" in stored:
        stored.add("entries")
    return {key for key in shape if key in stored}


def _ages(data: Mapping[str, Any]) -> tuple[int | None, int | None]:
    if "age_min" in data or "age_max" in data:
        return _int(data.get("age_min")), _int(data.get("age_max"))
    if data.get("age_range") is not None:
        return inclusive_age_bounds(data.get("age_range"))
    return None, None


def _entries(data: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    raw = data.get("entries")
    if raw is None:
        raw = data.get("weekly_entries")
    if not isinstance(raw, list):
        return []
    slots: list[tuple[int, int, int]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        day = item.get("day_of_week_utc", item.get("day_of_week"))
        start = item.get("start_minutes_utc", item.get("start_minutes"))
        end = item.get("end_minutes_utc", item.get("end_minutes"))
        if day is None or start is None or end is None:
            continue
        slots.append((int(day), int(start), int(end)))
    return sorted(slots)


def _translations(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    cleaned = {
        str(key): text
        for key, item in value.items()
        if (text := _text(item)) is not None
    }
    return dict(sorted(cleaned.items()))


def _urls(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item not in (None, "")]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(str(item) for item in value if _text(item))


def _norm_name(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    return normalize_org_name(text)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, "", "false", "False", 0, "0"):
        return False
    return bool(value)


def _quantize(value: Any, places: int) -> str | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    quant = Decimal("1").scaleb(-places)
    return format(number.quantize(quant), "f")
