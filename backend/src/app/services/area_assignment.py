"""Pick the geographic area a location is allowed to store."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased

from app.data.hk_neighbourhoods import CONFIDENT_RADIUS_KM
from app.data.hk_neighbourhoods import NEIGHBOURHOODS
from app.data.hk_neighbourhoods import assign_among
from app.data.hk_neighbourhoods import distance_km
from app.db.models import GeographicArea


def neighbourhood_children(
    session: Session, area: GeographicArea
) -> list[GeographicArea]:
    """Active neighbourhood rows directly under this area."""
    return list(
        session.scalars(
            select(GeographicArea)
            .where(
                GeographicArea.parent_id == area.id,
                GeographicArea.level == "neighbourhood",
                GeographicArea.active.is_(True),
            )
            .order_by(GeographicArea.display_order, GeographicArea.name)
        ).all()
    )


def is_leaf(session: Session, area_id: UUID) -> bool:
    """True when no geographic area lists this id as its parent."""
    child = session.scalar(
        select(GeographicArea.id).where(GeographicArea.parent_id == area_id).limit(1)
    )
    return child is None


def get_leaf(session: Session, area_id: UUID) -> GeographicArea | None:
    """The area when it exists and has no children."""
    child = aliased(GeographicArea)
    return session.scalar(
        select(GeographicArea)
        .outerjoin(child, child.parent_id == GeographicArea.id)
        .where(GeographicArea.id == area_id, child.id.is_(None))
    )


def resolve_leaf(
    session: Session,
    area: GeographicArea | None,
    lat: float | None,
    lng: float | None,
) -> GeographicArea | None:
    """Return a storable area.

    A district, region, or country that still has smaller areas becomes
    the nearest neighbourhood under it. An area that already has no
    children is returned unchanged. Missing coordinates use display order.
    """
    if area is None:
        return None
    leaves = _leaves_under(session, area)
    if not leaves:
        return area
    return _closest_leaf(area, leaves, lat, lng)


def assignment_is_confident(
    area: GeographicArea,
    leaves: list[GeographicArea],
    lat: float | None,
    lng: float | None,
) -> bool:
    """False when the pin is missing or farther than the review radius."""
    if lat is None or lng is None:
        return False
    choices = _catalog_choices(area, leaves)
    if choices:
        assigned = assign_among(choices, lat, lng)
        return assigned is not None and assigned.confident
    pinned = [row for row in leaves if row.lat is not None and row.lng is not None]
    if not pinned:
        return False
    nearest = min(
        pinned,
        key=lambda row: distance_km(float(row.lat), float(row.lng), lat, lng),
    )
    kilometres = distance_km(float(nearest.lat), float(nearest.lng), lat, lng)
    return kilometres <= CONFIDENT_RADIUS_KM


def _leaves_under(session: Session, area: GeographicArea) -> list[GeographicArea]:
    pending = [area.id]
    found: list[GeographicArea] = []
    seen: set[UUID] = set()
    while pending:
        rows = list(
            session.scalars(
                select(GeographicArea)
                .where(GeographicArea.parent_id.in_(pending))
                .order_by(GeographicArea.display_order, GeographicArea.name)
            ).all()
        )
        pending = []
        for row in rows:
            if row.id in seen:
                continue
            seen.add(row.id)
            found.append(row)
            pending.append(row.id)
    parent_ids = {row.parent_id for row in found}
    return [row for row in found if row.id not in parent_ids]


def _closest_leaf(
    area: GeographicArea,
    leaves: list[GeographicArea],
    lat: float | None,
    lng: float | None,
) -> GeographicArea:
    neighbourhoods = [row for row in leaves if row.level == "neighbourhood"] or leaves
    choices = _catalog_choices(area, neighbourhoods)
    if choices:
        assigned = assign_among(choices, lat, lng)
        if assigned is not None:
            match = next(
                (
                    row
                    for row in neighbourhoods
                    if row.name == assigned.neighbourhood.name
                ),
                None,
            )
            if match is not None:
                return match
    pinned = [
        row for row in neighbourhoods if row.lat is not None and row.lng is not None
    ]
    if lat is not None and lng is not None and pinned:
        return min(
            pinned,
            key=lambda row: distance_km(float(row.lat), float(row.lng), lat, lng),
        )
    return neighbourhoods[0]


def _catalog_choices(area: GeographicArea, leaves: list[GeographicArea]):
    if area.level == "district":
        names = {area.name}
    else:
        names = {
            item.district
            for item in NEIGHBOURHOODS
            if item.name in {row.name for row in leaves}
        }
        if not names:
            names = {row.name for row in leaves}
    return [item for item in NEIGHBOURHOODS if item.district in names]
