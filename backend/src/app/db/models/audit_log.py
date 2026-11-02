"""Audit log model."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


class AuditLog(Base):
    """Audit log entry for tracking data changes."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    table_name: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="Name of the table that was modified",
    )
    record_id: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="Primary key of the modified record",
    )
    action: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="INSERT, UPDATE, or DELETE",
    )
    user_id: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Cognito user sub who made the change",
    )
    request_id: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Lambda request ID for correlation",
    )
    old_values: Mapped[dict | None] = mapped_column(
        sa.dialects.postgresql.JSONB(),
        nullable=True,
        comment="Previous values (for UPDATE/DELETE)",
    )
    new_values: Mapped[dict | None] = mapped_column(
        sa.dialects.postgresql.JSONB(),
        nullable=True,
        comment="New values (for INSERT/UPDATE)",
    )
    changed_fields: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text()),
        nullable=True,
        comment="List of fields that changed (for UPDATE)",
    )
    source: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        server_default=text("'trigger'"),
        comment="Source of the audit entry: trigger or application",
    )
    ip_address: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Client IP address if available",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Client user agent if available",
    )
