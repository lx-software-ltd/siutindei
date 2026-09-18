"""Venue helpers for admin catalog import."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Activity, ActivityLocation, Location
from app.exceptions import ValidationError

LINKED_VENUE_WARNING = "linked existing activity to imported venue"


def resolve_single_imported_venue(
    cache: dict[str, Location],
) -> Location | None:
    """Return the single venue from this org payload, if any.

    Uses only locations imported in this request (the location cache).
    Does not fall back to venues already on the organization. Historical
    orphans are backfilled by Alembic ``0031_link_orphan_activities``.
    """
    unique: dict[str, Location] = {}
    for location in cache.values():
        unique[str(location.id)] = location
    if len(unique) == 1:
        return next(iter(unique.values()))
    return None


def link_activity_to_venue(
    session: Session,
    activity: Activity,
    venue: Location | None,
) -> bool:
    """Attach activity to a venue. Return True when a join row is added."""
    if venue is None:
        return False
    activity_id = activity.id
    location_id = venue.id
    existing = session.get(ActivityLocation, (activity_id, location_id))
    if existing is not None:
        return False
    session.add(
        ActivityLocation(
            activity_id=activity_id,
            location_id=location_id,
        )
    )
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValidationError(
            "failed to link activity venue",
            field="location",
        ) from exc
    return True
