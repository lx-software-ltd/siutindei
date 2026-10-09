"""Rules for venues that exist but are incomplete or inconsistent."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GeographicArea, Location
from app.services.location_fix_districts import district_key, pin_is_outside
from app.services.location_fix_geocode import geocode_address
from app.services.location_fixes import clear_pending, upsert_proposal

GEOCODE_CAP = 20


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
    geocodes_left: list[int],
) -> dict[str, Any] | None:
    """Highest-priority finding for one venue, or None when it is usable."""
    address = str(location.address or "").strip()
    if not address:
        return _unresolved("rule:empty_address", "Location has no address")
    if location.lat is None or location.lng is None:
        return _missing_coordinates(location, address, geocodes_left)
    key = district_key(areas)
    if key is not None and pin_is_outside(
        float(location.lat), float(location.lng), key
    ):
        name = areas[0].name if areas else key
        return _unresolved("rule:pin_outside_area", f"Map pin is outside {name}")
    if not str(location.place_id or "").strip():
        return _unresolved("rule:no_place_id", "Location has no Google place id")
    return None


def record_location_finding(
    session: Session,
    location: Location,
    areas: list[GeographicArea],
    run_id: str | UUID,
    geocodes_left: list[int],
) -> str:
    finding = assess_location(location, areas, geocodes_left)
    if finding is None:
        if clear_pending(session, "location", location.id):
            return "cleared"
        return "unchanged"
    return upsert_proposal(
        session,
        entity_type="location",
        entity_id=location.id,
        org_id=location.org_id,
        scan_run_id=run_id,
        **finding,
    )


def _missing_coordinates(
    location: Location,
    address: str,
    geocodes_left: list[int],
) -> dict[str, Any]:
    lat = None
    lng = None
    rationale = "Map pin will be looked up when you apply"
    if geocodes_left[0] > 0:
        geocodes_left[0] -= 1
        coords = geocode_address(address)
        if coords is None:
            rationale = "Address could not be geocoded; apply tries again"
        else:
            lat, lng = coords
            rationale = "Geocoded the stored address"
    proposed: dict[str, Any] = {
        "address": address,
        "area_id": str(location.area_id),
    }
    if lat is not None and lng is not None:
        proposed["lat"] = lat
        proposed["lng"] = lng
    return {
        "kind": "update_location",
        "source": "rule:missing_coordinates",
        "rationale": rationale,
        "target_location_id": location.id,
        "proposed_location": proposed,
    }


def _unresolved(source: str, rationale: str) -> dict[str, Any]:
    return {
        "kind": "unresolved",
        "source": source,
        "rationale": rationale,
        "target_location_id": None,
        "proposed_location": None,
    }
