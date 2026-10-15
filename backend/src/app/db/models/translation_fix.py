"""Translation sweeps and proposals for organization and activity text."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TranslationScanRun(Base):
    """One sweep of names and descriptions that still need a language."""

    __tablename__ = "translation_scan_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )
    requested_by: Mapped[str | None] = mapped_column(Text(), nullable=True)
    org_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_scope: Mapped[str] = mapped_column(Text(), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    total_entities: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default=text("0")
    )
    batches_total: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default=text("0")
    )
    batches_done: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default=text("0")
    )
    created_count: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default=text("0")
    )
    updated_count: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default=text("0")
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default=text("0")
    )
    cleared_count: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default=text("0")
    )
    queued_count: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default=text("0")
    )
    failed_count: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, server_default=text("0")
    )
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    truncated: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    processed_message_ids: Mapped[list[Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=list,
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
    finished_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')",
            name="translation_scan_status_check",
        ),
        CheckConstraint(
            "review_scope IN ('pending_review', 'all')",
            name="translation_scan_scope_check",
        ),
        CheckConstraint(
            "entity_type IS NULL OR entity_type IN ('organization', 'activity')",
            name="translation_scan_entity_check",
        ),
        Index(
            "translation_scan_one_active",
            text("(true)"),
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )


class TranslationFixProposal(Base):
    """One suggested fill-in for a missing name or description language."""

    __tablename__ = "translation_fix_proposals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    entity_type: Mapped[str] = mapped_column(Text(), nullable=False)
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    field: Mapped[str] = mapped_column(Text(), nullable=False)
    source_text: Mapped[dict[str, Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
    )
    proposed_text: Mapped[dict[str, Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
    )
    missing_languages: Mapped[list[Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=list,
    )
    source: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="model",
        server_default=text("'model'"),
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    scan_run_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("translation_scan_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    input_hash: Mapped[str | None] = mapped_column(Text(), nullable=True)
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
        CheckConstraint(
            "entity_type IN ('organization', 'activity')",
            name="translation_fix_entity_type_check",
        ),
        CheckConstraint(
            "field IN ('name', 'description')",
            name="translation_fix_field_check",
        ),
        CheckConstraint(
            "source IN ('model')",
            name="translation_fix_source_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'applied', 'dismissed')",
            name="translation_fix_status_check",
        ),
        Index(
            "translation_fix_one_pending",
            "entity_type",
            "entity_id",
            "field",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("translation_fix_org_idx", "org_id", "status"),
        Index("translation_fix_input_hash_idx", "input_hash"),
    )


class TranslationFixSettings(Base):
    """Singleton monthly budget for translation sweeps."""

    __tablename__ = "translation_fix_settings"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    monthly_cost_limit_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("50"),
        server_default=text("50"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="translation_fix_settings_singleton_check"),
        CheckConstraint(
            "monthly_cost_limit_usd > 0 AND monthly_cost_limit_usd <= 1000",
            name="translation_fix_settings_cost_check",
        ),
    )
