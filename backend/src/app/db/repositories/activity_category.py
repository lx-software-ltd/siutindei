"""Repository for ActivityCategory entities."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity
from app.db.models import ActivityCategory
from app.db.models.category_suggestion import PENDING_CATEGORY_ID
from app.db.repositories.base import BaseRepository
from app.exceptions import ValidationError


class ActivityCategoryRepository(BaseRepository[ActivityCategory]):
    """Repository for ActivityCategory CRUD operations."""

    def __init__(self, session: Session):
        """Initialize the repository.

        Args:
            session: SQLAlchemy session for database operations.
        """
        super().__init__(session, ActivityCategory)

    def get_all_flat(self) -> Sequence[ActivityCategory]:
        """Get all categories as a flat list.

        Returns:
            Categories ordered by display_order then name.
        """
        query = select(ActivityCategory).order_by(
            ActivityCategory.display_order,
            ActivityCategory.name,
            ActivityCategory.id,
        )
        return self._session.execute(query).scalars().all()

    def get_all_roots(self) -> Sequence[ActivityCategory]:
        """Get root categories (no parent)."""
        query = (
            select(ActivityCategory)
            .where(ActivityCategory.parent_id.is_(None))
            .order_by(ActivityCategory.display_order, ActivityCategory.name)
        )
        return self._session.execute(query).scalars().all()

    def get_children(self, parent_id: UUID) -> Sequence[ActivityCategory]:
        """Get direct children of a category."""
        query = (
            select(ActivityCategory)
            .where(ActivityCategory.parent_id == parent_id)
            .order_by(ActivityCategory.display_order, ActivityCategory.name)
        )
        return self._session.execute(query).scalars().all()

    def get_ancestors(self, category_id: UUID) -> list[ActivityCategory]:
        """Return the chain from root to this node."""
        chain: list[ActivityCategory] = []
        current = self.get_by_id(category_id)
        while current is not None:
            chain.append(current)
            if current.parent_id is None:
                break
            current = self.get_by_id(UUID(str(current.parent_id)))
        chain.reverse()
        return chain

    def delete(self, entity: ActivityCategory) -> None:
        """Delete a category if it has no children or activities."""
        category_id = _to_uuid(entity.id)
        if category_id == PENDING_CATEGORY_ID:
            raise ValidationError(
                "Pending categorisation cannot be deleted",
                field="id",
            )
        if self._has_children(category_id):
            raise ValidationError(
                "Cannot delete a category with subcategories",
                field="id",
            )
        if self._has_activities(category_id):
            raise ValidationError(
                "Cannot delete a category assigned to activities",
                field="id",
            )
        super().delete(entity)

    def _has_children(self, category_id: UUID) -> bool:
        """Return True if the category has children."""
        query = (
            select(ActivityCategory.id)
            .where(ActivityCategory.parent_id == category_id)
            .limit(1)
        )
        return self._session.execute(query).scalar() is not None

    def _has_activities(self, category_id: UUID) -> bool:
        """Return True if any activity uses the category."""
        query = select(Activity.id).where(Activity.category_id == category_id).limit(1)
        return self._session.execute(query).scalar() is not None


def _to_uuid(value: UUID | str) -> UUID:
    """Normalize a UUID value from str or UUID."""
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
