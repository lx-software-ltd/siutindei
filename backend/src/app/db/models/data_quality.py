"""Merge forwarding, duplicate dismissals, and name-fix proposals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


class OrganizationMerge(Base):
    """Forwarding row for an organization removed by a merge."""

    __tablename__ = "organization_merges"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    merged_org_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    survivor_org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    place_id: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False)
    moved_counts: Mapped[dict[str, Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
    )
    merged_by: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    merged_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class OrganizationDuplicateDismissal(Base):
    """Pair an admin has marked as not the same organization."""

    __tablename__ = "organization_duplicate_dismissals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    org_id_low: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id_high: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    dismissed_by: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    dismissed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id_low",
            "org_id_high",
            name="org_dup_dismissals_pair_key",
        ),
        CheckConstraint(
            "org_id_low <> org_id_high",
            name="org_dup_dismissals_distinct_check",
        ),
    )


class NameFixProposal(Base):
    """One suggested name change for an organization or activity."""

    __tablename__ = "name_fix_proposals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    entity_type: Mapped[str] = mapped_column(Text(), nullable=False)
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    field: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="name",
        server_default=text("'name'"),
    )
    current_value: Mapped[str] = mapped_column(Text(), nullable=False)
    proposed_value: Mapped[str] = mapped_column(Text(), nullable=False)
    rules: Mapped[list[Any]] = mapped_column(JSONB(), nullable=False, default=list)
    translation_patch: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB(),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    scan_run_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    decided_by: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
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

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('organization', 'activity')",
            name="name_fix_entity_type_check",
        ),
        CheckConstraint(
            "field = 'name'",
            name="name_fix_field_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'applied', 'dismissed')",
            name="name_fix_status_check",
        ),
    )


class NameFixSettings(Base):
    """Singleton rule toggles for name cleanup."""

    __tablename__ = "name_fix_settings"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    enabled_rules: Mapped[list[Any]] = mapped_column(JSONB(), nullable=False)
    exception_words: Mapped[list[Any]] = mapped_column(JSONB(), nullable=False)
    bracket_suffixes: Mapped[list[Any]] = mapped_column(JSONB(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="name_fix_settings_singleton_check"),
    )
