"""Import job model for idempotent catalog imports."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


class ImportJob(Base):
    """Stored result for a catalog import object_key."""

    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    object_key: Mapped[str] = mapped_column(Text(), nullable=False)
    dry_run: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        server_default=text("false"),
    )
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB(),
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB(),
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    file_warnings: Mapped[list[str]] = mapped_column(
        JSONB(),
        nullable=False,
        server_default=text("'[]'::jsonb"),
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
