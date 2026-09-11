"""First-party listing funnel event models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base

NIL_LOCATION_ID = UUID("00000000-0000-0000-0000-000000000000")

LISTING_EVENT_TYPES = (
    "search",
    "listing_view",
    "cta_tap",
    "lead_relayed",
)

LISTING_EVENT_SOURCES = (
    "public_www",
    "flutter",
    "partner",
)


class ListingEvent(Base):
    """Raw first-party listing interaction (search, view, CTA, lead)."""

    __tablename__ = "listing_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('search', 'listing_view', 'cta_tap', " "'lead_relayed')",
            name="listing_events_type_allowed",
        ),
        CheckConstraint(
            "source IN ('public_www', 'flutter', 'partner')",
            name="listing_events_source_allowed",
        ),
        Index(
            "listing_events_day_type_idx",
            "occurred_on",
            "event_type",
            "location_id",
        ),
        Index(
            "listing_events_client_id_uniq",
            "source",
            "client_event_id",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    occurred_on: Mapped[date] = mapped_column(Date(), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    event_type: Mapped[str] = mapped_column(Text(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("'00000000-0000-0000-0000-000000000000'"),
    )
    activity_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(Text(), nullable=False)
    client_event_id: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ListingEventsDaily(Base):
    """Daily listing funnel counts by location for v_funnel_daily."""

    __tablename__ = "listing_events_daily"

    day: Mapped[date] = mapped_column(Date(), primary_key=True)
    location_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("'00000000-0000-0000-0000-000000000000'"),
    )
    searches: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        server_default=text("0"),
    )
    listing_views: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        server_default=text("0"),
    )
    cta_taps: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        server_default=text("0"),
    )
    leads_relayed: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        server_default=text("0"),
    )
    bookings_confirmed: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        server_default=text("0"),
    )
