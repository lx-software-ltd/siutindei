"""Repository for OrganizationFeedback entities."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import OrganizationFeedback
from app.db.repositories.base import BaseRepository


class OrganizationFeedbackRepository(BaseRepository[OrganizationFeedback]):
    """Repository for organization feedback CRUD operations."""

    def __init__(self, session: Session):
        """Initialize the repository."""
        super().__init__(session, OrganizationFeedback)

    def get_all(
        self,
        limit: int = 50,
        cursor: UUID | None = None,
    ) -> Sequence[OrganizationFeedback]:
        """Get feedback entries with cursor pagination."""
        query = select(OrganizationFeedback).order_by(OrganizationFeedback.id)
        if cursor is not None:
            query = query.where(OrganizationFeedback.id > cursor)
        return self._session.execute(query.limit(limit)).scalars().all()
