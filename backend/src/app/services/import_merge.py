"""Per-field three-way merge for a catalog import row.

Base is what the source last said. Live is the catalog row. File is
the incoming row. Comparison uses the same normalisation as version 1.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.services.catalog_version_shape import (
    ACTIVITY_SHAPE_KEYS,
    LOCATION_SHAPE_KEYS,
    ORG_SHAPE_KEYS,
    PRICING_SHAPE_KEYS,
    SCHEDULE_SHAPE_KEYS,
    build_shape,
)

PROPOSED_PREFIX = "Proposed: "

_PRESENT = {
    "organization": set(ORG_SHAPE_KEYS),
    "activity": set(ACTIVITY_SHAPE_KEYS),
    "location": set(LOCATION_SHAPE_KEYS),
    "pricing": set(PRICING_SHAPE_KEYS),
    "schedule": set(SCHEDULE_SHAPE_KEYS) | {"weekly_entries"},
}


@dataclass(frozen=True)
class FieldChange:
    """One field decision, with the three values the admin can see."""

    field: str
    action: str
    base: Any
    current: Any
    proposed: Any


@dataclass(frozen=True)
class RowPlan:
    """What the importer should write for one existing or new row.

    ``apply_fields`` is ``None`` when every provided field may be
    written (today's row-level update). An empty set writes nothing.
    """

    status: str | None
    apply_fields: frozenset[str] | None
    changes: tuple[FieldChange, ...] = ()
    warnings: tuple[str, ...] = ()


def merge_mode(
    existing_rows: str,
    approved_organizations: str,
    review_status: str | None,
) -> str:
    """Policy for one organization. Approved rows use their own dial."""
    if review_status == "approved":
        return approved_organizations
    return existing_rows


def decide_fields(
    entity_type: str,
    base: Mapping[str, Any] | None,
    live: Mapping[str, Any],
    incoming: Mapping[str, Any],
    present: set[str],
    *,
    mode: str,
    only: set[str] | None = None,
) -> RowPlan:
    """Decide each file field. ``mode`` is ``merge`` or ``propose``."""
    base_shape = build_shape(entity_type, base or {})
    live_shape = build_shape(entity_type, live)
    overlaid = dict(base or {})
    for key in present:
        if key in incoming:
            overlaid[key] = incoming[key]
    if "weekly_entries" in present or "entries" in present:
        overlaid["entries"] = incoming.get("weekly_entries", incoming.get("entries"))
    if "age_min" in present or "age_max" in present:
        overlaid.pop("age_range", None)
    file_shape = build_shape(entity_type, overlaid)
    changes: list[FieldChange] = []
    for field in _fields(entity_type, present, only):
        key = _shape_key(field)
        base_value = base_shape.get(key)
        live_value = live_shape.get(key)
        file_value = file_shape.get(key)
        action = _action(base_value, live_value, file_value, mode)
        changes.append(
            FieldChange(
                field=field,
                action=action,
                base=jsonable(base_value),
                current=jsonable(live_value),
                proposed=jsonable(_raw_proposed(incoming, field, file_value)),
            )
        )
    return _plan(changes)


def next_payload(
    entity_type: str,
    base: Mapping[str, Any] | None,
    incoming: Mapping[str, Any],
    present: set[str],
) -> dict[str, Any]:
    """Shape to store as what the source now says.

    Omitted file fields keep the previous base. Entries are stored as
    objects so a later comparison parses them again.
    """
    overlaid: dict[str, Any] = dict(base or {})
    for key in present:
        if key in incoming:
            overlaid[key] = incoming[key]
    if "weekly_entries" in present or "entries" in present:
        overlaid["entries"] = incoming.get("weekly_entries", incoming.get("entries"))
    if "age_min" in present or "age_max" in present:
        overlaid.pop("age_range", None)
    shape = build_shape(entity_type, overlaid)
    stored = jsonable(shape)
    if entity_type == "schedule":
        stored["entries"] = [
            {
                "day_of_week_utc": day,
                "start_minutes_utc": start,
                "end_minutes_utc": end,
            }
            for day, start, end in shape.get("entries") or []
        ]
    return stored


def jsonable(value: Any) -> Any:
    """JSON value for a baseline or a proposal column."""
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def same_json(left: Any, right: Any) -> bool:
    """True when two stored JSON values are the same proposal."""
    return jsonable(left) == jsonable(right)


def _plan(changes: list[FieldChange]) -> RowPlan:
    applied = tuple(change.field for change in changes if change.action == "apply")
    proposed = tuple(change for change in changes if change.action == "proposal")
    warnings: list[str] = []
    if proposed:
        names = ", ".join(change.field for change in proposed)
        warnings.append(f"{PROPOSED_PREFIX}{names}")
    if applied:
        return RowPlan(
            status=None,
            apply_fields=frozenset(applied),
            changes=tuple(changes),
            warnings=tuple(warnings),
        )
    if proposed:
        return RowPlan(
            status="proposed",
            apply_fields=frozenset(),
            changes=tuple(changes),
            warnings=tuple(warnings),
        )
    return RowPlan(
        status="unchanged",
        apply_fields=frozenset(),
        changes=tuple(changes),
        warnings=tuple(warnings),
    )


def _action(base: Any, live: Any, file: Any, mode: str) -> str:
    if file == base:
        return "keep"
    if live == file:
        return "keep"
    if mode == "propose" or live != base:
        return "proposal"
    return "apply"


def _fields(entity_type: str, present: set[str], only: set[str] | None) -> list[str]:
    allowed = _PRESENT[entity_type]
    names: list[str] = []
    for key in sorted(present & allowed):
        field = "weekly_entries" if key == "entries" else key
        if field == "entries":
            continue
        if only is not None and _shape_key(field) not in only:
            continue
        if field not in names:
            names.append(field)
    return names


def _shape_key(field: str) -> str:
    if field == "weekly_entries":
        return "entries"
    return field


def _raw_proposed(incoming: Mapping[str, Any], field: str, shaped: Any) -> Any:
    if field == "weekly_entries":
        raw = incoming.get("weekly_entries", incoming.get("entries"))
        return raw if raw is not None else shaped
    if field in incoming:
        return incoming[field]
    return shaped
