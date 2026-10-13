"""Stored catalog versions.

Rows outlive the catalog record they describe. Deletes and merges leave
the version-1 snapshot in place so a later import can recognise it.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


class CatalogVersion(Base):
    """One version of an organization, media set, or child catalog row."""

    __tablename__ = "catalog_versions"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('organization', 'media', 'location', "
            "'activity', 'pricing', 'schedule')",
            name="catalog_versions_entity_type_check",
        ),
        CheckConstraint(
            "action IN ('created', 'updated', 'deleted')",
            name="catalog_versions_action_check",
        ),
        CheckConstraint("version > 0", name="catalog_versions_version_check"),
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "version",
            name="catalog_versions_entity_version_key",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    entity_type: Mapped[str] = mapped_column(Text(), nullable=False)
    entity_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    org_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer(), nullable=False)
    action: Mapped[str] = mapped_column(Text(), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    changed_fields: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text()),
        nullable=True,
    )
    txid: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    import_job_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    related_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
