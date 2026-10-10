"""Pick the geographic area a location is allowed to store."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.hk_neighbourhoods import nearest_in_district
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


def resolve_leaf(
    session: Session,
    area: GeographicArea | None,
    lat: float | None,
    lng: float | None,
) -> GeographicArea | None:
    """Return a storable area.

    A district that has neighbourhoods becomes the nearest one. An area
    that already has no children is returned unchanged.
    """
    if area is None:
        return None
    children = neighbourhood_children(session, area)
    if not children:
        return area
    picked = nearest_in_district(area.name, lat, lng)
    if picked is not None:
        match = next((child for child in children if child.name == picked.name), None)
        if match is not None:
            return match
    return children[0]
