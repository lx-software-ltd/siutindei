"""Version-1 gates for catalog import upserts."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Activity, Location, Organization
from app.services.catalog_version_match import apply_child_gate
from app.services.catalog_version_payload import (
    activity_payload,
    location_payload,
    pricing_payload,
    schedule_payload,
)

_ACTIVITY_KEYS = (
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


def hold_existing(
    existing: Any,
    terminal: str | None,
    allow_updates: bool,
) -> tuple[Any, str] | None:
    """Return a finished upsert result when the row must not be written."""
    if terminal:
        return existing, terminal
    if existing is not None and not allow_updates:
        return existing, "skipped"
    return None


def location_terminal(
    session: Session,
    org: Organization,
    existing: Location | None,
    body: dict[str, Any],
    address_value: str,
    allow_updates: bool,
    warnings: list[str] | None,
) -> str | None:
    incoming = {**body, "address": address_value}
    return apply_child_gate(
        session,
        entity_type="location",
        org_id=org.id,
        live=existing,
        incoming=incoming,
        present={
            key
            for key in ("address", "area_id", "lat", "lng", "place_id")
            if key in incoming
        },
        current=location_payload(existing) if existing else None,
        allow_updates=allow_updates,
        warnings=warnings,
    )


def activity_terminal(
    session: Session,
    org: Organization,
    existing: Activity | None,
    raw_activity: dict[str, Any],
    body: dict[str, Any],
    name: str,
    allow_updates: bool,
    warnings: list[str] | None,
) -> str | None:
    return apply_child_gate(
        session,
        entity_type="activity",
        org_id=org.id,
        live=existing,
        incoming=body,
        present={key for key in _ACTIVITY_KEYS if key in body or key in raw_activity},
        current=activity_payload(existing) if existing else None,
        allow_updates=allow_updates,
        warnings=warnings,
        names={name, str(body.get("name") or name)},
    )


def pricing_terminal(
    session: Session,
    activity: Activity,
    location: Location,
    existing: Any,
    body: dict[str, Any],
    allow_updates: bool,
) -> str | None:
    incoming = {
        **body,
        "location_address": location.address,
        "activity_id": str(activity.id),
        "location_id": str(location.id),
    }
    return apply_child_gate(
        session,
        entity_type="pricing",
        org_id=activity.org_id,
        live=existing,
        incoming=incoming,
        present=set(body) | {"location_address"},
        current=pricing_payload(existing, location) if existing else None,
        allow_updates=allow_updates,
        warnings=None,
    )


def schedule_terminal(
    session: Session,
    activity: Activity,
    location: Location,
    existing: Any,
    languages: list[str],
    entries: list[dict[str, int]],
    allow_updates: bool,
    warnings: list[str],
) -> str | None:
    incoming = {
        "languages": languages,
        "weekly_entries": entries,
        "location_address": location.address,
        "activity_id": str(activity.id),
        "location_id": str(location.id),
    }
    return apply_child_gate(
        session,
        entity_type="schedule",
        org_id=activity.org_id,
        live=existing,
        incoming=incoming,
        present={"languages", "weekly_entries", "location_address"},
        current=schedule_payload(existing, location) if existing else None,
        allow_updates=allow_updates,
        warnings=warnings,
    )
