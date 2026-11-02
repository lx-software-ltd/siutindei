"""Repository for partner API key entities."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import ApiKey
from app.db.repositories.base import BaseRepository


class ApiKeyRepository(BaseRepository[ApiKey]):
    """Repository for partner API key CRUD operations."""

    def __init__(self, session: Session):
        """Initialize the repository.

        Args:
            session: SQLAlchemy session for database operations.
        """
        super().__init__(session, ApiKey)

    def find_active_by_hash(self, key_hash: str) -> ApiKey | None:
        """Find an active (non-revoked, non-expired) key by its hash.

        Args:
            key_hash: SHA-256 hex digest of the plaintext key.

        Returns:
            The matching active key, or None.
        """
        now = datetime.now(UTC)
        query = select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.revoked_at.is_(None),
            or_(ApiKey.expires_at.is_(None), ApiKey.expires_at > now),
        )
        return self._session.execute(query).scalar_one_or_none()

    def revoke(self, api_key: ApiKey) -> ApiKey:
        """Mark a key as revoked (idempotent).

        Args:
            api_key: The key entity to revoke.

        Returns:
            The revoked key entity.
        """
        if api_key.revoked_at is None:
            api_key.revoked_at = datetime.now(UTC)
        return self.update(api_key)

    def touch_last_used(self, api_key: ApiKey) -> None:
        """Update last_used_at to the current time.

        Args:
            api_key: The key entity to touch.
        """
        api_key.last_used_at = datetime.now(UTC)
        self._session.add(api_key)
        self._session.flush()
