"""Location sweeps and venue proposals for organizations and activities."""

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

_SOURCES = (
    "'rule:single_location', 'rule:pricing_schedule', 'rule:name_area', "
    "'rule:no_venue', 'model', 'rule:missing_coordinates', "
    "'rule:empty_address', 'rule:pin_outside_area'"
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LocationScanRun(Base):
    """One sweep of organizations and activities that still need a venue."""

    __tablename__ = "location_scan_runs"

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
    auto_applied_count: Mapped[int] = mapped_column(
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
            name="location_scan_status_check",
        ),
        CheckConstraint(
            "review_scope IN ('pending_review', 'all')",
            name="location_scan_scope_check",
        ),
        CheckConstraint(
            "entity_type IS NULL OR entity_type IN "
            "('organization', 'activity', 'location')",
            name="location_scan_entity_check",
        ),
        Index(
            "location_scan_one_active",
            text("(true)"),
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )


class LocationFixProposal(Base):
    """One suggested venue link or new location."""

    __tablename__ = "location_fix_proposals"

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
    kind: Mapped[str] = mapped_column(Text(), nullable=False)
    target_location_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposed_location: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(Text(), nullable=False)
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
        ForeignKey("location_scan_runs.id", ondelete="SET NULL"),
        nullable=True,
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
        CheckConstraint(
            "entity_type IN ('organization', 'activity', 'location')",
            name="location_fix_entity_type_check",
        ),
        CheckConstraint(
            "kind IN ("
            "'link_existing', 'create_location', 'unresolved', 'update_location')",
            name="location_fix_kind_check",
        ),
        CheckConstraint(
            f"source IN ({_SOURCES})",
            name="location_fix_source_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'applied', 'dismissed')",
            name="location_fix_status_check",
        ),
        Index(
            "location_fix_one_pending",
            "entity_type",
            "entity_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )


class LocationFixSettings(Base):
    """Singleton monthly budget for location-model sweeps."""

    __tablename__ = "location_fix_settings"

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
        CheckConstraint("id = 1", name="location_fix_settings_singleton_check"),
        CheckConstraint(
            "monthly_cost_limit_usd > 0 AND monthly_cost_limit_usd <= 1000",
            name="location_fix_settings_cost_check",
        ),
    )
