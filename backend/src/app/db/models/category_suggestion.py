"""Category suggestion queue and admin settings."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID as UUIDType
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base

PENDING_CATEGORY_ID = UUIDType("c1111111-1111-1111-1111-111111111199")
SETTINGS_SINGLETON_ID = UUIDType("c2222222-2222-2222-2222-222222222201")
PENDING_CATEGORY_NAME = "Pending categorisation"
DEFAULT_OPENROUTER_MODEL = "qwen/qwen3-30b-a3b"
DEFAULT_FALLBACK_MODELS = ("qwen/qwen-turbo",)


class CategorySuggestionSettings(Base):
    """Singleton admin settings for category capture and OpenRouter."""

    __tablename__ = "category_suggestion_settings"

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    on_import_enabled: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    auto_enrich_enabled: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    openrouter_model: Mapped[str | None] = mapped_column(Text(), nullable=True)
    fallback_models: Mapped[list[str]] = mapped_column(
        ARRAY(Text()),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
    )
    max_evidence_items: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=25,
        server_default=text("25"),
    )
    deny_data_collection: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    auto_assign_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3),
        nullable=True,
        default=Decimal("0.900"),
        server_default=text("0.900"),
    )
    monthly_cost_limit_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("25"),
        server_default=text("25"),
    )
    updated_by: Mapped[str | None] = mapped_column(Text(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "max_evidence_items BETWEEN 5 AND 50",
            name="cat_sug_settings_evidence_check",
        ),
        CheckConstraint(
            "auto_assign_threshold IS NULL OR "
            "(auto_assign_threshold >= 0.5 AND auto_assign_threshold <= 1)",
            name="cat_sug_settings_threshold_check",
        ),
        CheckConstraint(
            "monthly_cost_limit_usd > 0 AND monthly_cost_limit_usd <= 1000",
            name="cat_sug_settings_cost_check",
        ),
    )


class CategorySuggestion(Base):
    """One proposed category, keyed by the normalised requested name."""

    __tablename__ = "category_suggestions"

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    fingerprint: Mapped[str] = mapped_column(Text(), nullable=False, unique=True)
    requested_name: Mapped[str] = mapped_column(Text(), nullable=False)
    source: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="import",
        server_default=text("'import'"),
    )
    status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    enrichment_status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="none",
        server_default=text("'none'"),
    )
    enrichment_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    model_used: Mapped[str | None] = mapped_column(Text(), nullable=True)
    suggested_name: Mapped[str | None] = mapped_column(Text(), nullable=True)
    name_translations: Mapped[dict[str, str]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    suggested_parent_id: Mapped[UUIDType | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activity_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    maps_to_category_id: Mapped[UUIDType | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activity_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text(), nullable=True)
    alternatives: Mapped[dict[str, Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    usage: Mapped[dict[str, Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_category_id: Mapped[UUIDType | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activity_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    merged_into_category_id: Mapped[UUIDType | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activity_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_by: Mapped[str | None] = mapped_column(Text(), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    decision_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    activity_count: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    reopened_at: Mapped[datetime | None] = mapped_column(
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
            "source IN ('import', 'scan')",
            name="cat_sug_source_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'merged', 'rejected')",
            name="cat_sug_status_check",
        ),
        CheckConstraint(
            "enrichment_status IN ('none', 'queued', 'running', 'done', 'failed')",
            name="cat_sug_enrich_check",
        ),
    )


class CategorySuggestionActivity(Base):
    """Evidence link from a suggestion to an imported activity."""

    __tablename__ = "category_suggestion_activities"

    suggestion_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("category_suggestions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    activity_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    org_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    import_job_id: Mapped[UUIDType | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_name: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
