"""Website enrichment runs, proposals, and the monthly budget."""

from __future__ import annotations

from datetime import datetime
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

RUN_STATUSES = (
    "queued",
    "running",
    "extracting",
    "ready",
    "failed",
    "render_required",
)
PROPOSAL_STATUSES = ("pending", "applied", "dismissed", "superseded")
ACTIVE_RUN_STATUSES = ("queued", "running", "extracting")


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class OrgEnrichmentRun(Base):
    """One crawl-and-extract pass for a single organization."""

    __tablename__ = "org_enrichment_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )
    requested_by: Mapped[str | None] = mapped_column(Text(), nullable=True)
    seed_url: Mapped[str] = mapped_column(Text(), nullable=False)
    pages: Mapped[list[Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    pages_fetched: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    bytes_fetched: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    model: Mapped[str | None] = mapped_column(Text(), nullable=True)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    input_hash: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    processed_message_ids: Mapped[list[Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
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
            "status IN ('queued', 'running', 'extracting', 'ready', "
            "'failed', 'render_required')",
            name="org_enrichment_runs_status_check",
        ),
        Index(
            "org_enrichment_runs_active_org_idx",
            "org_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running', 'extracting')"),
        ),
        Index("org_enrichment_runs_org_idx", "org_id", "created_at"),
    )


class OrgEnrichmentProposal(Base):
    """One suggested change, applied only after an admin accepts it."""

    __tablename__ = "org_enrichment_proposals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("org_enrichment_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    section: Mapped[str] = mapped_column(Text(), nullable=False)
    kind: Mapped[str] = mapped_column(Text(), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    field: Mapped[str | None] = mapped_column(Text(), nullable=True)
    label: Mapped[str] = mapped_column(Text(), nullable=False)
    current_value: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(),
        nullable=True,
    )
    proposed_value: Mapped[dict[str, Any]] = mapped_column(
        JSONB(),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    unverified: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    evidence: Mapped[list[Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    proposed_hash: Mapped[str] = mapped_column(Text(), nullable=False)
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
            "status IN ('pending', 'applied', 'dismissed', 'superseded')",
            name="org_enrichment_proposals_status_check",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="org_enrichment_proposals_confidence_check",
        ),
        Index("org_enrichment_proposals_run_idx", "run_id"),
        Index("org_enrichment_proposals_org_idx", "org_id", "status"),
    )


class OrgEnrichmentSettings(Base):
    """Singleton budget and crawl limits for website enrichment."""

    __tablename__ = "org_enrichment_settings"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    monthly_cost_limit_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("25"),
        server_default=text("25"),
    )
    max_pages: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=12,
        server_default=text("12"),
    )
    max_page_bytes: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=1_000_000,
        server_default=text("1000000"),
    )
    copy_media: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    min_confidence_shown: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        default=Decimal("0.500"),
        server_default=text("0.500"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="org_enrichment_settings_singleton_check"),
        CheckConstraint(
            "monthly_cost_limit_usd > 0 AND monthly_cost_limit_usd <= 1000",
            name="org_enrichment_settings_cost_check",
        ),
        CheckConstraint(
            "max_pages >= 1 AND max_pages <= 20",
            name="org_enrichment_settings_pages_check",
        ),
        CheckConstraint(
            "max_page_bytes >= 10000 AND max_page_bytes <= 2000000",
            name="org_enrichment_settings_bytes_check",
        ),
        CheckConstraint(
            "min_confidence_shown >= 0 AND min_confidence_shown <= 1",
            name="org_enrichment_settings_confidence_check",
        ),
    )
