"""Organization model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, text
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
    name_key: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Normalized name for duplicate matching; maintained by trigger",
    )
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
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
    phone_country_code: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="ISO 3166-1 alpha-2 country code for phone number",
    )
    phone_number: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="National phone number digits (no country code)",
    )
    email: Mapped[str | None] = mapped_column(Text(), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(Text(), nullable=True)
    facebook: Mapped[str | None] = mapped_column(Text(), nullable=True)
    instagram: Mapped[str | None] = mapped_column(Text(), nullable=True)
    tiktok: Mapped[str | None] = mapped_column(Text(), nullable=True)
    twitter: Mapped[str | None] = mapped_column(Text(), nullable=True)
    xiaohongshu: Mapped[str | None] = mapped_column(Text(), nullable=True)
    wechat: Mapped[str | None] = mapped_column(Text(), nullable=True)
    website: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Organization website",
    )
    media_urls: Mapped[list[str]] = mapped_column(
        ARRAY(Text()),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    logo_media_url: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
    )
    place_id: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="operational",
        server_default=text("'operational'"),
    )
    status_changed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    status_source: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source_id: Mapped[str | None] = mapped_column(Text(), nullable=True)
    description_source: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
    )
    source_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    review_status: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        default="pending_review",
        server_default=text("'pending_review'"),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Cognito sub of the admin who last set review_status",
    )
    review_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Why review_status is rejected",
    )
    import_job_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_imported_at: Mapped[datetime | None] = mapped_column(
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
    version: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    media_version: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    locations: Mapped[list[Location]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    activities: Mapped[list[Activity]] = relationship(
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
        CheckConstraint(
            "review_status IN ('pending_review', 'approved', 'rejected')",
            name="organizations_review_status_check",
        ),
        CheckConstraint(
            "review_reason IS NULL OR review_reason IN "
            "('not_relevant', 'duplicate', 'poor_data', 'other')",
            name="organizations_review_reason_check",
        ),
        CheckConstraint(
            "review_reason IS NULL OR review_status = 'rejected'",
            name="organizations_review_reason_rejected_check",
        ),
    )
