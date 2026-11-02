"""Ticket model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base
from app.db.models.enums import TicketStatus, TicketType


class Ticket(Base):
    """Ticket submitted by a user for admin review."""

    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    ticket_id: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        unique=True,
        comment="Unique progressive ticket ID (prefix + 5 digits)",
    )
    ticket_type: Mapped[TicketType] = mapped_column(
        sa.Enum(
            TicketType,
            name="ticket_type",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
        comment="Discriminator for ticket type and workflow",
    )
    submitter_id: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="Cognito user sub of the person who submitted",
    )
    submitter_email: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="Email of the submitter for notifications",
    )
    organization_name: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="Organization name referenced by this ticket",
    )
    message: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Free-text message from the submitter",
    )
    status: Mapped[TicketStatus] = mapped_column(
        sa.Enum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
        server_default=text("'pending'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="When the ticket was reviewed",
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Cognito user sub of the admin who reviewed",
    )
    admin_notes: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Notes from the reviewing admin",
    )

    organization_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="Organization referenced by feedback tickets",
    )
    feedback_stars: Mapped[int | None] = mapped_column(
        sa.SmallInteger(),
        nullable=True,
        comment="Feedback rating from 0 to 5",
    )
    feedback_label_ids: Mapped[list[str]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default=text("'{}'::uuid[]"),
        comment="Selected feedback label IDs",
    )
    feedback_text: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Free-form feedback description",
    )

    description: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Extended description",
    )
    suggested_district: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="District or area",
    )
    suggested_address: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Full address",
    )
    suggested_lat: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6),
        nullable=True,
        comment="Latitude coordinate",
    )
    suggested_lng: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6),
        nullable=True,
        comment="Longitude coordinate",
    )
    media_urls: Mapped[list[str]] = mapped_column(
        ARRAY(Text()),
        nullable=False,
        server_default=text("'{}'::text[]"),
        comment="URLs of uploaded media files",
    )
    created_organization_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to organization created or assigned on approval",
    )
