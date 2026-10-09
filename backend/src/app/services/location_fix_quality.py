"""Rules for venues that exist but are incomplete or inconsistent."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GeographicArea, Location
from app.services.location_fix_districts import district_key, pin_is_outside
from app.services.location_fixes import clear_pending, pending_row, upsert_proposal


def area_chains(
    session: Session, area_ids: list[Any]
) -> dict[Any, list[GeographicArea]]:
    """Each area id mapped to itself, then its parents."""
    pending = {area_id for area_id in area_ids if area_id is not None}
    loaded: dict[Any, GeographicArea] = {}
    while pending:
        rows = list(
            session.scalars(
                select(GeographicArea).where(GeographicArea.id.in_(pending))
            ).all()
        )
        pending = set()
        for area in rows:
            loaded[area.id] = area
        for area in rows:
            if area.parent_id is not None and area.parent_id not in loaded:
                pending.add(area.parent_id)
    chains: dict[Any, list[GeographicArea]] = {}
    for area_id in list(loaded):
        chain: list[GeographicArea] = []
        seen: set[Any] = set()
        current: GeographicArea | None = loaded.get(area_id)
        while current is not None and current.id not in seen:
            chain.append(current)
            seen.add(current.id)
            parent_id = current.parent_id
            current = loaded.get(parent_id) if parent_id is not None else None
        chains[area_id] = chain
    return chains


def assess_location(
    location: Location,
    areas: list[GeographicArea],
) -> dict[str, Any] | None:
    """Highest-priority finding for one venue, or None when it is usable."""
    address = str(location.address or "").strip()
    if not address:
        return _unresolved("rule:empty_address", "Location has no address")
    if location.lat is None or location.lng is None:
        return _missing_coordinates(location, address)
    key = district_key(areas)
    if key is not None and pin_is_outside(
        float(location.lat), float(location.lng), key
    ):
        name = areas[0].name if areas else key
        return _unresolved(
            "rule:pin_outside_area",
            f"Map pin is outside {name}",
            proposed_location={
                "lat": float(location.lat),
                "lng": float(location.lng),
            },
        )
    return None


def record_location_finding(
    session: Session,
    location: Location,
    areas: list[GeographicArea],
    run_id: str | UUID,
    pending: set[tuple[str, Any]] | None = None,
) -> str:
    """Store or clear the venue finding. `pending` is the sweep's preloaded set."""
    finding = assess_location(location, areas)
    if finding is None:
        if pending is not None and ("location", location.id) not in pending:
            return "unchanged"
        if clear_pending(session, "location", location.id):
            return "cleared"
        return "unchanged"
    _keep_lookup(session, location.id, finding)
    return upsert_proposal(
        session,
        entity_type="location",
        entity_id=location.id,
        org_id=location.org_id,
        scan_run_id=run_id,
        **finding,
    )


def _keep_lookup(session: Session, location_id, finding: dict[str, Any]) -> None:
    """A later sweep must not drop a pin lookup that is still fresh."""
    proposed = finding.get("proposed_location")
    if not isinstance(proposed, dict) or proposed.get("lookup"):
        return
    existing = pending_row(session, "location", location_id)
    if existing is None:
        return
    stored = existing.proposed_location or {}
    lookup = stored.get("lookup")
    if not lookup:
        return
    proposed["lookup"] = lookup
    for key in ("lat", "lng"):
        if stored.get(key) is not None:
            proposed[key] = stored[key]
    if existing.source in {"lookup:nominatim", "lookup:google"}:
        finding["source"] = existing.source


def _missing_coordinates(location: Location, address: str) -> dict[str, Any]:
    """Store the address only. A single apply looks up the pin."""
    return {
        "kind": "update_location",
        "source": "rule:missing_coordinates",
        "rationale": "Map pin will be looked up when you apply",
        "target_location_id": location.id,
        "proposed_location": {
            "address": address,
            "area_id": str(location.area_id),
        },
    }


def _unresolved(
    source: str,
    rationale: str,
    proposed_location: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": "unresolved",
        "source": source,
        "rationale": rationale,
        "target_location_id": None,
        "proposed_location": proposed_location,
    }
