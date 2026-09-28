"""Activity-related models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, INT4RANGE, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base
from app.db.models.enums import PricingType, ScheduleType

if TYPE_CHECKING:
    from app.db.models.activity_category import ActivityCategory
    from app.db.models.location import Location
    from app.db.models.organization import Organization


class Activity(Base):
    """Activity offered by an organization."""

    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activity_categories.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK to activity_categories",
    )
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    name_translations: Mapped[dict[str, str]] = mapped_column(
        sa.dialects.postgresql.JSONB(),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Language map for non-English name translations",
    )
    description_translations: Mapped[dict[str, str]] = mapped_column(
        sa.dialects.postgresql.JSONB(),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Language map for non-English description translations",
    )
    source_url: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    source_note: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    age_range: Mapped[object] = mapped_column(INT4RANGE(), nullable=False)
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

    organization: Mapped["Organization"] = relationship(back_populates="activities")
    category: Mapped["ActivityCategory"] = relationship(back_populates="activities")
    locations: Mapped[List["ActivityLocation"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan",
    )
    pricing: Mapped[List["ActivityPricing"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan",
    )
    schedules: Mapped[List["ActivitySchedule"]] = relationship(
        back_populates="activity",
        cascade="all, delete-orphan",
    )


class ActivityLocation(Base):
    """Association between activities and locations."""

    __tablename__ = "activity_locations"

    activity_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        primary_key=True,
    )

    activity: Mapped["Activity"] = relationship(back_populates="locations")
    location: Mapped["Location"] = relationship()


class ActivityPricing(Base):
    """Pricing for an activity at a specific location."""

    __tablename__ = "activity_pricing"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    activity_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
    )
    pricing_type: Mapped[PricingType] = mapped_column(
        sa.Enum(
            PricingType,
            name="pricing_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text(), nullable=False, server_default="HKD")
    sessions_count: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    free_trial_class_offered: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    __table_args__ = (
        CheckConstraint(
            "(pricing_type <> 'per_sessions') OR "
            "(sessions_count IS NOT NULL AND sessions_count > 0)",
            name="pricing_sessions_count_check",
        ),
    )

    activity: Mapped["Activity"] = relationship(back_populates="pricing")
    location: Mapped["Location"] = relationship(back_populates="activity_pricing")


class ActivitySchedule(Base):
    """Schedule definition for an activity at a location."""

    __tablename__ = "activity_schedule"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    activity_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
    )
    schedule_type: Mapped[ScheduleType] = mapped_column(
        sa.Enum(
            ScheduleType,
            name="schedule_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    languages: Mapped[List[str]] = mapped_column(
        ARRAY(Text()),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )

    __table_args__ = (
        CheckConstraint(
            "schedule_type = 'weekly'",
            name="schedule_type_weekly_only",
        ),
        UniqueConstraint(
            "activity_id",
            "location_id",
            "languages",
            name="schedule_unique_activity_location_languages",
        ),
    )

    activity: Mapped["Activity"] = relationship(back_populates="schedules")
    location: Mapped["Location"] = relationship(back_populates="activity_schedules")
    entries: Mapped[List["ActivityScheduleEntry"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by=(
            "ActivityScheduleEntry.day_of_week_utc, "
            "ActivityScheduleEntry.start_minutes_utc, "
            "ActivityScheduleEntry.id"
        ),
    )


class ActivityScheduleEntry(Base):
    """Weekly schedule entry for a schedule definition."""

    __tablename__ = "activity_schedule_entries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    schedule_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activity_schedule.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week_utc: Mapped[int] = mapped_column(SmallInteger(), nullable=False)
    start_minutes_utc: Mapped[int] = mapped_column(Integer(), nullable=False)
    end_minutes_utc: Mapped[int] = mapped_column(Integer(), nullable=False)

    schedule: Mapped["ActivitySchedule"] = relationship(back_populates="entries")

    __table_args__ = (
        CheckConstraint(
            "day_of_week_utc BETWEEN 0 AND 6",
            name="schedule_entry_day_range",
        ),
        CheckConstraint(
            "start_minutes_utc BETWEEN 0 AND 1439",
            name="schedule_entry_start_minutes_range",
        ),
        CheckConstraint(
            "end_minutes_utc BETWEEN 0 AND 1439",
            name="schedule_entry_end_minutes_range",
        ),
        CheckConstraint(
            "start_minutes_utc != end_minutes_utc",
            name="schedule_entry_minutes_order",
        ),
        UniqueConstraint(
            "schedule_id",
            "day_of_week_utc",
            "start_minutes_utc",
            "end_minutes_utc",
            name="schedule_entry_unique",
        ),
    )
