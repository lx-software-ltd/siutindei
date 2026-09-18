"""Repository for Location entities."""

from __future__ import annotations

from typing import Optional
from typing import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Location
from app.db.repositories.base import BaseRepository


class LocationRepository(BaseRepository[Location]):
    """Repository for Location CRUD operations."""

    def __init__(self, session: Session):
        """Initialize the repository.

        Args:
            session: SQLAlchemy session for database operations.
        """
        super().__init__(session, Location)

    def find_by_organization(
        self,
        org_id: UUID,
        limit: int = 50,
        cursor: Optional[UUID] = None,
    ) -> Sequence[Location]:
        """Find all locations for an organization.

        Args:
            org_id: The organization UUID.
            limit: Maximum results to return.
            cursor: Pagination cursor.

        Returns:
            Locations belonging to the organization.
        """
        query = select(Location).where(Location.org_id == org_id).order_by(Location.id)
        if cursor is not None:
            query = query.where(Location.id > cursor)
        return self._session.execute(query.limit(limit)).scalars().all()

    def find_by_area(
        self,
        area_id: UUID,
        limit: int = 50,
    ) -> Sequence[Location]:
        """Find locations by geographic area.

        Args:
            area_id: The geographic area UUID.
            limit: Maximum results to return.

        Returns:
            Locations in the specified area.
        """
        query = (
            select(Location)
            .where(Location.area_id == area_id)
            .order_by(Location.id)
            .limit(limit)
        )
        return self._session.execute(query).scalars().all()

    def find_by_place_id(self, place_id: str) -> Optional[Location]:
        """Find a location by Google place_id."""
        query = select(Location).where(Location.place_id == place_id)
        return self._session.execute(query).scalar_one_or_none()

    def find_by_org_and_address(
        self,
        org_id: UUID,
        address: str,
    ) -> Optional[Location]:
        """Find a location by organization and address."""
        query = (
            select(Location)
            .where(Location.org_id == org_id)
            .where(Location.address == address)
        )
        return self._session.execute(query).scalar_one_or_none()

    def find_by_org_and_address_case_insensitive(
        self,
        org_id: UUID,
        address: str,
    ) -> Optional[Location]:
        """Find a location by org and case-insensitive address."""
        normalized = address.strip()
        query = (
            select(Location)
            .where(Location.org_id == org_id)
            .where(
                func.lower(func.trim(Location.address))
                == func.lower(func.trim(normalized))
            )
        )
        return self._session.execute(query).scalar_one_or_none()
