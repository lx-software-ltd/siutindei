"""Turn an accepted venue proposal into locations and join rows."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.admin_resource_location import _create_location
from app.db.models import Activity, ActivityLocation, Location
from app.db.models.location_fix import LocationFixProposal
from app.db.repositories import LocationRepository
from app.exceptions import NotFoundError, ValidationError
from app.services.location_fix_geocode import geocode_address
from app.services.location_fix_query import pending_row


def apply_proposal(
    session: Session,
    row: LocationFixProposal,
    *,
    address: str | None,
    area_id: str | None,
    target_location_id: str | UUID | None = None,
) -> None:
    if row.kind == "unresolved":
        if target_location_id is not None:
            _apply_candidate(session, row, target_location_id)
            return
        raise ValidationError("Nothing to apply", field="kind")
    if row.kind == "link_existing":
        _apply_link(session, row)
        return
    if row.kind == "create_location":
        _apply_create(session, row, address=address, area_id=area_id)
        return
    if row.kind == "update_location":
        _apply_update(session, row)
        return
    raise ValidationError("Invalid kind", field="kind")


def _apply_candidate(
    session: Session, row: LocationFixProposal, target_location_id: str | UUID
) -> None:
    if row.entity_type != "activity":
        raise ValidationError("Only an activity can link a venue", field="entity_type")
    candidates = (row.proposed_location or {}).get("candidates") or []
    allowed = {
        str(item.get("location_id"))
        for item in candidates
        if isinstance(item, dict) and item.get("location_id")
    }
    if str(target_location_id) not in allowed:
        raise ValidationError("Location is not a candidate", field="target_location_id")
    row.kind = "link_existing"
    row.target_location_id = str(target_location_id)
    _apply_link(session, row)


def _apply_update(session: Session, row: LocationFixProposal) -> None:
    if row.entity_type != "location":
        raise ValidationError("Only a location can be geocoded", field="entity_type")
    location = session.get(Location, row.entity_id)
    if location is None:
        raise NotFoundError("locations", str(row.entity_id))
    proposed = dict(row.proposed_location or {})
    stored_address = str(location.address or "").strip()
    proposed_address = str(proposed.get("address") or "").strip()
    if not stored_address:
        raise ValidationError("address is required", field="address")
    if proposed_address and proposed_address != stored_address:
        raise ValidationError("Address changed since the sweep", field="address")
    lat = proposed.get("lat")
    lng = proposed.get("lng")
    if lat is None or lng is None:
        coords = geocode_address(stored_address)
        if coords is None:
            raise ValidationError("Address could not be geocoded", field="address")
        lat, lng = coords
    location.lat = Decimal(str(lat))
    location.lng = Decimal(str(lng))
    proposed["lat"] = float(lat)
    proposed["lng"] = float(lng)
    proposed["address"] = stored_address
    row.proposed_location = proposed
    row.target_location_id = location.id


def _apply_link(session: Session, row: LocationFixProposal) -> None:
    if row.entity_type != "activity":
        raise ValidationError("Only an activity can link a venue", field="entity_type")
    if row.target_location_id is None:
        raise ValidationError(
            "target_location_id is required", field="target_location_id"
        )
    location = session.get(Location, row.target_location_id)
    activity = session.get(Activity, row.entity_id)
    if activity is None:
        raise NotFoundError("activities", str(row.entity_id))
    if location is None or str(location.org_id) != str(activity.org_id):
        raise ValidationError(
            "Location is no longer on this organization",
            field="target_location_id",
        )
    existing = session.get(ActivityLocation, (activity.id, location.id))
    if existing is None:
        session.add(ActivityLocation(activity_id=activity.id, location_id=location.id))
        session.flush()


def _apply_create(
    session: Session,
    row: LocationFixProposal,
    *,
    address: str | None,
    area_id: str | None,
) -> None:
    proposed = dict(row.proposed_location or {})
    stored_address = str(proposed.get("address") or "").strip()
    chosen_address = stored_address if address is None else address.strip()
    chosen_area = str(area_id or proposed.get("area_id") or "").strip()
    if not chosen_address:
        raise ValidationError("address is required", field="address")
    if not chosen_area:
        raise ValidationError("area_id is required", field="area_id")
    lat = proposed.get("lat")
    lng = proposed.get("lng")
    if chosen_address != stored_address:
        lat = None
        lng = None
    if lat is None or lng is None:
        coords = geocode_address(chosen_address)
        if coords is not None:
            lat, lng = coords
    location = _create_location(
        LocationRepository(session),
        {
            "org_id": str(row.org_id),
            "area_id": chosen_area,
            "address": chosen_address,
            "lat": lat,
            "lng": lng,
            "place_id": proposed.get("place_id"),
        },
    )
    session.add(location)
    session.flush()
    proposed["address"] = chosen_address
    proposed["area_id"] = chosen_area
    proposed["lat"] = None if lat is None else float(lat)
    proposed["lng"] = None if lng is None else float(lng)
    row.proposed_location = proposed
    row.target_location_id = location.id
    _link_sole_venue(session, row.org_id, location.id)


def _link_sole_venue(
    session: Session, org_id: str | UUID, location_id: str | UUID
) -> None:
    """When the org now has one venue, link every activity still without one."""
    count = session.scalar(
        select(func.count()).select_from(Location).where(Location.org_id == org_id)
    )
    if int(count or 0) != 1:
        return
    linked = select(ActivityLocation.activity_id)
    orphans = session.scalars(
        select(Activity).where(
            Activity.org_id == org_id,
            Activity.id.not_in(linked),
        )
    ).all()
    for activity in orphans:
        session.add(ActivityLocation(activity_id=activity.id, location_id=location_id))
        pending = pending_row(session, "activity", activity.id)
        if pending is not None:
            session.delete(pending)
    session.flush()
