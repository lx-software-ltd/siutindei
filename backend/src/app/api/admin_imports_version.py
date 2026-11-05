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
from app.services.import_merge import RowPlan

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
    plan: RowPlan,
    allow_updates: bool,
) -> tuple[Any, str] | None:
    """Return a finished upsert result when the row must not be written."""
    if plan.status:
        return existing, plan.status
    if existing is not None and not allow_updates:
        return existing, "skipped"
    return None


def restrict_import_body(body: dict[str, Any], plan: RowPlan) -> None:
    """Keep only the fields the merge plan allows the file to write."""
    if plan.apply_fields is None:
        return
    for key in list(body):
        if key not in plan.apply_fields:
            body.pop(key, None)


def stage_source_category(body: dict[str, Any]) -> None:
    """Show the file label to the merge before category resolution."""
    name = body.get("category_name")
    if isinstance(name, str) and name.strip():
        body["source_category_name"] = name.strip()


def keep_applied_category(body: dict[str, Any], plan: RowPlan) -> str | None:
    """Keep a resolved category id when the source label is applied."""
    capture_name = body.pop("_capture_category_name", None)
    category_id = body.pop("category_id", None)
    if (
        plan.apply_fields is not None
        and "source_category_name" not in plan.apply_fields
    ):
        capture_name = None
        category_id = None
    restrict_import_body(body, plan)
    if category_id is not None:
        body["category_id"] = category_id
    return capture_name


def remember_created(
    session: Any,
    entity_type: str,
    entity_id: Any,
    org_id: Any,
    payload: dict[str, Any],
    *,
    source: str | None = None,
) -> None:
    """Store the created row, including defaults the file left out."""
    from app.db.repositories.import_baseline import save_baseline
    from app.services.import_merge import next_payload

    save_baseline(
        session,
        entity_type,
        entity_id,
        org_id,
        next_payload(entity_type, payload, payload, set(payload)),
        source=source,
    )


def location_terminal(
    session: Session,
    org: Organization,
    existing: Location | None,
    body: dict[str, Any],
    address_value: str,
    allow_updates: bool,
    warnings: list[str] | None,
) -> RowPlan:
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
) -> RowPlan:
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
) -> RowPlan:
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
) -> RowPlan:
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
