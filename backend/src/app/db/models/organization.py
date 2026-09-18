"""Organization model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import CheckConstraint, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.activity import Activity
    from app.db.models.location import Location


class Organization(Base):
    """Organization that provides activities."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    name_translations: Mapped[dict[str, str]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Language map for non-English name translations",
    )
    description_translations: Mapped[dict[str, str]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Language map for non-English description translations",
    )
    manager_id: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="Cognito user sub (subject) identifier of the organization manager",
    )
    phone_country_code: Mapped[Optional[str]] = mapped_column(
        Text(),
        nullable=True,
        comment="ISO 3166-1 alpha-2 country code for phone number",
    )
    phone_number: Mapped[Optional[str]] = mapped_column(
        Text(),
        nullable=True,
        comment="National phone number digits (no country code)",
    )
    email: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    whatsapp: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    facebook: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    instagram: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    tiktok: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    twitter: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    xiaohongshu: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    wechat: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    media_urls: Mapped[List[str]] = mapped_column(
        ARRAY(Text()),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    logo_media_url: Mapped[Optional[str]] = mapped_column(
        Text(),
        nullable=True,
    )
    place_id: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="operational",
        server_default=text("'operational'"),
    )
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    status_source: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    description_source: Mapped[Optional[str]] = mapped_column(
        Text(),
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

    locations: Mapped[List["Location"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    activities: Mapped[List["Activity"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('operational', 'closed_temporarily', "
            "'closed_permanently', 'hidden')",
            name="organizations_status_check",
        ),
        CheckConstraint(
            "status_source IS NULL OR status_source IN "
            "('owner', 'provider', 'places', 'importer')",
            name="organizations_status_source_check",
        ),
        CheckConstraint(
            "description_source IS NULL OR description_source IN "
            "('template', 'official', 'places', 'enrich')",
            name="organizations_desc_source_check",
        ),
    )
