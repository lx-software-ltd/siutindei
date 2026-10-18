"""Import behaviour settings and data-quality runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID as UUIDType
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class ImportSettings(Base):
    """Singleton controls for what an import does."""

    __tablename__ = "import_settings"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    skip_deleted_organizations: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    name_cleanup: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="apply",
        server_default=text("'apply'"),
    )
    unknown_categories: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="capture",
        server_default=text("'capture'"),
    )
    duplicates: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="off",
        server_default=text("'off'"),
    )
    locations: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="off",
        server_default=text("'off'"),
    )
    categories: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="off",
        server_default=text("'off'"),
    )
    updated_by: Mapped[str | None] = mapped_column(Text(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="import_settings_singleton_check"),
        CheckConstraint(
            "name_cleanup IN ('off', 'propose', 'apply')",
            name="import_settings_name_cleanup_check",
        ),
        CheckConstraint(
            "unknown_categories IN ('capture', 'fail')",
            name="import_settings_unknown_categories_check",
        ),
        CheckConstraint(
            "duplicates IN ('off', 'report')",
            name="import_settings_duplicates_check",
        ),
        CheckConstraint(
            "locations IN ('off', 'check')",
            name="import_settings_locations_check",
        ),
        CheckConstraint(
            "categories IN ('off', 'check')",
            name="import_settings_categories_check",
        ),
    )


class DataQualityRun(Base):
    """One import, enrichment, or manual pass over the data-quality checks."""

    __tablename__ = "data_quality_runs"

    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    trigger: Mapped[str] = mapped_column(Text(), nullable=False)
    import_job_id: Mapped[UUIDType | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_by: Mapped[str | None] = mapped_column(Text(), nullable=True)
    scope: Mapped[dict[str, Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
    )
    checks: Mapped[list[Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=list,
    )
    status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )
    attempt: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    attempts: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    refresh: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    config_hash: Mapped[str] = mapped_column(Text(), nullable=False)
    check_versions: Mapped[dict[str, Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text(), nullable=True)
    processed_message_ids: Mapped[list[Any]] = mapped_column(
        JSONB(),
        nullable=False,
        default=list,
    )
    as_of: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
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
            "trigger IN ('import', 'manual', 'enrichment')",
            name="data_quality_runs_trigger_check",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'done', 'partial', 'failed', 'busy')",
            name="data_quality_runs_status_check",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="data_quality_runs_idempotency_key",
        ),
        Index(
            "data_quality_runs_import_job_idx",
            "import_job_id",
            "attempt",
            unique=True,
            postgresql_where=text("import_job_id IS NOT NULL"),
        ),
    )


class ModelAnswer(Base):
    """One recorded model reply for a hashed prompt and model."""

    __tablename__ = "model_answers"

    key_hash: Mapped[str] = mapped_column(Text(), primary_key=True)
    model: Mapped[str] = mapped_column(Text(), nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text(), nullable=False)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )


class LookupAnswer(Base):
    """One recorded geocoder reply for a hashed query."""

    __tablename__ = "lookup_answers"

    key_hash: Mapped[str] = mapped_column(Text(), primary_key=True)
    provider: Mapped[str] = mapped_column(Text(), nullable=False)
    query: Mapped[str] = mapped_column(Text(), nullable=False)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("now()"),
    )
