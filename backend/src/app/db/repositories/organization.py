"""Repository for Organization entities."""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Organization
from app.db.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for Organization CRUD operations."""

    def __init__(self, session: Session):
        """Initialize the repository.

        Args:
            session: SQLAlchemy session for database operations.
        """
        super().__init__(session, Organization)

    def find_by_name(self, name: str) -> Optional[Organization]:
        """Find an organization by exact name.

        Args:
            name: The organization name.

        Returns:
            The organization if found, None otherwise.
        """
        query = select(Organization).where(Organization.name == name)
        return self._session.execute(query).scalar_one_or_none()

    def find_by_name_case_insensitive(self, name: str) -> Optional[Organization]:
        """Find an organization by case-insensitive name."""
        normalized = name.strip()
        query = select(Organization).where(
            func.lower(func.trim(Organization.name))
            == func.lower(func.trim(normalized))
        )
        return self._session.execute(query).scalar_one_or_none()

    def find_by_place_id(self, place_id: str) -> Optional[Organization]:
        """Find an organization by Google place_id."""
        query = select(Organization).where(Organization.place_id == place_id)
        return self._session.execute(query).scalar_one_or_none()

    def find_by_source_id(self, source_id: str) -> Optional[Organization]:
        """Find an organization by parsed catalog source_id."""
        query = select(Organization).where(Organization.source_id == source_id)
        return self._session.execute(query).scalar_one_or_none()

    def find_by_manager_and_name(
        self,
        manager_id: str,
        name: str,
    ) -> Optional[Organization]:
        """Find by manager and case-insensitive trimmed name."""
        query = (
            select(Organization)
            .where(
                func.lower(func.trim(Organization.manager_id))
                == manager_id.strip().lower()
            )
            .where(func.lower(func.trim(Organization.name)) == name.strip().lower())
        )
        return self._session.execute(query).scalar_one_or_none()

    def find_by_manager(
        self,
        manager_id: str,
        limit: int = 50,
    ) -> Sequence[Organization]:
        """Find organizations managed by a specific Cognito user.

        Args:
            manager_id: The Cognito user sub (subject) identifier.
            limit: Maximum results to return.

        Returns:
            Organizations managed by the specified user.
        """
        query = (
            select(Organization)
            .where(Organization.manager_id == manager_id)
            .order_by(Organization.name)
            .limit(limit)
        )
        return self._session.execute(query).scalars().all()

    def search_by_name(
        self,
        name_pattern: str,
        limit: int = 50,
    ) -> Sequence[Organization]:
        """Search organizations by name pattern (case-insensitive).

        Args:
            name_pattern: Pattern to search for.
            limit: Maximum results to return.

        Returns:
            Matching organizations.
        """
        # Escape LIKE special characters to prevent pattern injection
        escaped = _escape_like_pattern(name_pattern)
        query = (
            select(Organization)
            .where(Organization.name.ilike(f"%{escaped}%"))
            .order_by(Organization.name)
            .limit(limit)
        )
        return self._session.execute(query).scalars().all()

    def create_organization(
        self,
        name: str,
        manager_id: str,
        description: Optional[str] = None,
        media_urls: Optional[Sequence[str]] = None,
    ) -> Organization:
        """Create a new organization.

        Args:
            name: Organization name.
            manager_id: Cognito user sub for the organization manager.
            description: Optional description.
            media_urls: Optional list of media URLs.

        Returns:
            The created organization.
        """
        org = Organization(
            name=name,
            manager_id=manager_id,
            description=description,
            media_urls=list(media_urls or []),
        )
        return self.create(org)

    def update_organization(
        self,
        organization: Organization,
        name: Optional[str] = None,
        description: Optional[str] = None,
        media_urls: Optional[Sequence[str]] = None,
    ) -> Organization:
        """Update an organization.

        Args:
            organization: The organization to update.
            name: New name (if provided).
            description: New description (if provided).
            media_urls: New media URLs (if provided).

        Returns:
            The updated organization.
        """
        if name is not None:
            organization.name = name
        if description is not None:
            organization.description = description
        if media_urls is not None:
            organization.media_urls = list(media_urls)
        return self.update(organization)


def _escape_like_pattern(pattern: str) -> str:
    """Escape LIKE pattern special characters.

    Prevents users from injecting wildcards into search patterns.

    Args:
        pattern: The search pattern to escape.

    Returns:
        The escaped pattern safe for use in LIKE queries.
    """
    # Escape backslash first, then percent and underscore
    return pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
