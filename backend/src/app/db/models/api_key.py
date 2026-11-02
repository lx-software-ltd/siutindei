"""Partner API key model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base


class ApiKey(Base):
    """API key used to authenticate partner API requests.

    Only a SHA-256 hash of the key is stored; the plaintext value is
    returned exactly once when the key is created.
    """

    __tablename__ = "api_keys"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('read', 'crud')",
            name="api_keys_scope_allowed",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="Human-readable label for the key (e.g. partner name)",
    )
    key_prefix: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="First characters of the plaintext key, for display",
    )
    key_hash: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        unique=True,
        comment="SHA-256 hex digest of the plaintext key",
    )
    scope: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="Access scope: read (query only) or crud (query + edit)",
    )
    org_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="Restrict the key to one organization; NULL = full access",
    )
    created_by: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Cognito sub of the admin who created the key",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Optional expiry; NULL = does not expire",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Set when the key is revoked; NULL = active",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
