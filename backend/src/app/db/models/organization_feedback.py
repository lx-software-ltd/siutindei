"""Organization feedback model."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


class OrganizationFeedback(Base):
    """Approved feedback for an organization."""

    __tablename__ = "organization_feedback"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    submitter_id: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Cognito user sub for the submitter",
    )
    submitter_email: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Submitter email for reference",
    )
    stars: Mapped[int] = mapped_column(
        sa.SmallInteger(),
        nullable=False,
        comment="Star rating from 0 to 5",
    )
    label_ids: Mapped[list[str]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default=text("'{}'::uuid[]"),
        comment="List of feedback label IDs",
    )
    description: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Free-form feedback description",
    )
    source_ticket_id: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Source feedback ticket ID, if applicable",
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

    organization = relationship("Organization")
