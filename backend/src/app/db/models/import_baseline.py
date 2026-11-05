"""What a catalog source last said, and fields waiting on an admin."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import CheckConstraint, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base

_ENTITY = (
    "entity_type IN ('organization', 'location', 'activity', 'pricing', 'schedule')"
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ImportBaseline(Base):
    """Normalised file shape from the last import that saw this entity."""

    __tablename__ = "import_baselines"

    entity_type: Mapped[str] = mapped_column(Text(), primary_key=True)
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    org_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source: Mapped[str | None] = mapped_column(Text(), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False)
    import_job_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(_ENTITY, name="import_baselines_entity_type_check"),
    )


class ImportChangeProposal(Base):
    """One field where the source and the catalog both moved."""

    __tablename__ = "import_change_proposals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    entity_type: Mapped[str] = mapped_column(Text(), nullable=False)
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    org_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    field: Mapped[str] = mapped_column(Text(), nullable=False)
    base_value: Mapped[Any] = mapped_column(JSONB(), nullable=True)
    current_value: Mapped[Any] = mapped_column(JSONB(), nullable=True)
    proposed_value: Mapped[Any] = mapped_column(JSONB(), nullable=True)
    import_job_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    decided_by: Mapped[str | None] = mapped_column(Text(), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(_ENTITY, name="import_change_proposals_entity_type_check"),
        CheckConstraint(
            "status IN ('pending', 'applied', 'dismissed')",
            name="import_change_proposals_status_check",
        ),
        Index("import_change_proposals_org_idx", "org_id", "status"),
    )
