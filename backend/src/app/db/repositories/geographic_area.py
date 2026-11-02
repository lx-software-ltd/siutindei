"""Repository for GeographicArea entities."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GeographicArea


class GeographicAreaRepository:
    """Repository for geographic area lookups and management."""

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self._session = session

    def get_by_id(self, area_id: UUID) -> GeographicArea | None:
        """Get a geographic area by its ID.

        Args:
            area_id: The area UUID.

        Returns:
            The area or None if not found.
        """
        return self._session.get(GeographicArea, area_id)

    def get_all_roots(self, active_only: bool = True) -> Sequence[GeographicArea]:
        """Get all root (country-level) areas.

        Args:
            active_only: If True, only return active countries.

        Returns:
            Country-level geographic areas.
        """
        query = (
            select(GeographicArea)
            .where(GeographicArea.parent_id.is_(None))
            .order_by(GeographicArea.display_order)
        )
        if active_only:
            query = query.where(GeographicArea.active.is_(True))
        return self._session.execute(query).scalars().all()

    def get_children(self, parent_id: UUID) -> Sequence[GeographicArea]:
        """Get direct children of a geographic area.

        Args:
            parent_id: Parent area UUID.

        Returns:
            Direct child areas, ordered by display_order.
        """
        query = (
            select(GeographicArea)
            .where(GeographicArea.parent_id == parent_id)
            .order_by(GeographicArea.display_order)
        )
        return self._session.execute(query).scalars().all()

    def get_all_flat(self, active_only: bool = True) -> Sequence[GeographicArea]:
        """Get all geographic areas as a flat list.

        Used to build the tree on the client side.

        Args:
            active_only: If True, only return areas under active countries.

        Returns:
            All geographic areas.
        """
        if active_only:
            # Fetch all and filter in Python (simple approach for small tree)
            all_areas = (
                self._session.execute(
                    select(GeographicArea).order_by(GeographicArea.display_order)
                )
                .scalars()
                .all()
            )
            # Build a set of active area IDs
            active_ids: set[str] = set()
            # Find active countries
            for a in all_areas:
                if a.parent_id is None and a.active:
                    active_ids.add(str(a.id))
            # Walk descendants
            changed = True
            while changed:
                changed = False
                for a in all_areas:
                    pid = str(a.parent_id) if a.parent_id else None
                    if pid and pid in active_ids and str(a.id) not in active_ids:
                        active_ids.add(str(a.id))
                        changed = True
            return [a for a in all_areas if str(a.id) in active_ids]
        else:
            return (
                self._session.execute(
                    select(GeographicArea).order_by(GeographicArea.display_order)
                )
                .scalars()
                .all()
            )

    def toggle_active(self, area_id: UUID, active: bool) -> GeographicArea | None:
        """Toggle the active flag on a geographic area (typically a country).

        Args:
            area_id: The area UUID.
            active: New active state.

        Returns:
            The updated area, or None if not found.
        """
        area = self.get_by_id(area_id)
        if area is None:
            return None
        area.active = active
        self._session.flush()
        return area

    def get_ancestors(self, area_id: UUID) -> list[GeographicArea]:
        """Walk up the tree and return the chain from root to this node.

        Args:
            area_id: Starting area UUID.

        Returns:
            List from root (country) down to the given area.
        """
        chain: list[GeographicArea] = []
        current = self.get_by_id(area_id)
        while current is not None:
            chain.append(current)
            if current.parent_id is None:
                break
            current = self.get_by_id(UUID(str(current.parent_id)))
        chain.reverse()
        return chain

    def resolve_country_and_district(self, area_id: UUID) -> tuple[str, str]:
        """Resolve country name and district name from an area_id.

        Walks up the tree to find the root (country) and uses the
        leaf as the district.

        Args:
            area_id: The leaf area UUID.

        Returns:
            Tuple of (country_name, district_name).

        Raises:
            ValueError: If area_id is invalid.
        """
        ancestors = self.get_ancestors(area_id)
        if not ancestors:
            raise ValueError(f"Geographic area {area_id} not found")
        country = ancestors[0].name  # root = country
        district = ancestors[-1].name  # leaf = most specific
        return country, district
