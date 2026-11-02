"""Repository for tickets.

This module provides data access methods for the tickets table.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Ticket, TicketStatus, TicketType
from app.db.repositories.base import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    """Repository for unified ticket operations."""

    def __init__(self, session: Session):
        """Initialize the repository.

        Args:
            session: SQLAlchemy session for database operations.
        """
        super().__init__(session, Ticket)

    def find_by_ticket_id(
        self,
        ticket_id: str,
    ) -> Ticket | None:
        """Find a ticket by its ticket ID.

        Used for idempotency checks in async processing.

        Args:
            ticket_id: The unique ticket ID (e.g., R00001 or S00001).

        Returns:
            The ticket if found.
        """
        query = select(Ticket).where(Ticket.ticket_id == ticket_id)
        return self._session.execute(query).scalar_one_or_none()

    def find_pending_by_submitter(
        self,
        submitter_id: str,
        ticket_type: TicketType | None = None,
    ) -> Ticket | None:
        """Find a pending ticket for a specific user.

        Args:
            submitter_id: Cognito user sub.
            ticket_type: Optional filter by ticket type.

        Returns:
            The pending ticket if found.
        """
        query = (
            select(Ticket)
            .where(Ticket.submitter_id == submitter_id)
            .where(Ticket.status == TicketStatus.PENDING)
        )
        if ticket_type:
            query = query.where(Ticket.ticket_type == ticket_type)
        query = query.order_by(Ticket.created_at.desc()).limit(1)
        return self._session.execute(query).scalar_one_or_none()

    def find_by_submitter(
        self,
        submitter_id: str,
        ticket_type: TicketType | None = None,
        limit: int = 50,
        cursor: UUID | None = None,
    ) -> Sequence[Ticket]:
        """Find tickets by submitter.

        Args:
            submitter_id: Cognito user sub of the submitter.
            ticket_type: Optional filter by ticket type.
            limit: Maximum number of results.
            cursor: Pagination cursor.

        Returns:
            Sequence of tickets by this user.
        """
        query = (
            select(Ticket)
            .where(Ticket.submitter_id == submitter_id)
            .order_by(Ticket.created_at.desc())
        )
        if ticket_type:
            query = query.where(Ticket.ticket_type == ticket_type)
        if cursor:
            query = query.where(Ticket.id > cursor)
        return self._session.execute(query.limit(limit)).scalars().all()

    def find_all(
        self,
        ticket_type: TicketType | None = None,
        status: TicketStatus | None = None,
        limit: int = 50,
        cursor: UUID | None = None,
    ) -> Sequence[Ticket]:
        """Find all tickets with optional filters.

        Args:
            ticket_type: Filter by ticket type.
            status: Filter by ticket status.
            limit: Maximum number of results.
            cursor: Pagination cursor.

        Returns:
            Sequence of tickets.
        """
        query = select(Ticket).order_by(Ticket.created_at.desc())
        if ticket_type:
            query = query.where(Ticket.ticket_type == ticket_type)
        if status:
            query = query.where(Ticket.status == status)
        if cursor:
            query = query.where(Ticket.id > cursor)
        return self._session.execute(query.limit(limit)).scalars().all()

    def count_pending(
        self,
        ticket_type: TicketType | None = None,
    ) -> int:
        """Count pending tickets.

        Args:
            ticket_type: Optional filter by ticket type.

        Returns:
            Number of pending tickets.
        """
        query = (
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.status == TicketStatus.PENDING)
        )
        if ticket_type:
            query = query.where(Ticket.ticket_type == ticket_type)
        return self._session.execute(query).scalar() or 0
