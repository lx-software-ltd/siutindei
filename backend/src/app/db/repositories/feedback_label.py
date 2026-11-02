"""Repository for FeedbackLabel entities."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FeedbackLabel, OrganizationFeedback, Ticket
from app.db.repositories.base import BaseRepository
from app.exceptions import ValidationError


class FeedbackLabelRepository(BaseRepository[FeedbackLabel]):
    """Repository for feedback label CRUD operations."""

    def __init__(self, session: Session):
        """Initialize the repository."""
        super().__init__(session, FeedbackLabel)

    def get_all_sorted(self) -> Sequence[FeedbackLabel]:
        """Get all feedback labels ordered for display."""
        query = select(FeedbackLabel).order_by(
            FeedbackLabel.display_order,
            FeedbackLabel.name,
            FeedbackLabel.id,
        )
        return self._session.execute(query).scalars().all()

    def get_by_ids(self, label_ids: Iterable[UUID]) -> Sequence[FeedbackLabel]:
        """Get labels by ID list."""
        ids = list(label_ids)
        if not ids:
            return []
        query = select(FeedbackLabel).where(FeedbackLabel.id.in_(ids))
        return self._session.execute(query).scalars().all()

    def delete(self, entity: FeedbackLabel) -> None:
        """Delete label if it is not used anywhere."""
        label_id = _to_uuid(entity.id)
        if self._is_used(label_id):
            raise ValidationError(
                "Cannot delete a label that is used in feedback",
                field="id",
            )
        super().delete(entity)

    def _is_used(self, label_id: UUID) -> bool:
        """Return True if the label is used by any feedback entry."""
        ticket_query = (
            select(Ticket.id)
            .where(Ticket.feedback_label_ids.any(label_id))  # type: ignore[arg-type]
            .limit(1)
        )
        feedback_query = (
            select(OrganizationFeedback.id)
            .where(OrganizationFeedback.label_ids.any(label_id))  # type: ignore[arg-type]
            .limit(1)
        )
        return (
            self._session.execute(ticket_query).scalar() is not None
            or self._session.execute(feedback_query).scalar() is not None
        )


def _to_uuid(value: UUID | str) -> UUID:
    """Normalize a UUID value from str or UUID."""
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
