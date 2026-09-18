"""Location model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.activity import ActivityPricing, ActivitySchedule
    from app.db.models.geographic_area import GeographicArea
    from app.db.models.organization import Organization


class Location(Base):
    """Location for an organization."""

    __tablename__ = "locations"

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
    area_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geographic_areas.id"),
        nullable=False,
        comment="FK to geographic_areas leaf node",
    )
    address: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    place_id: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
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

    organization: Mapped["Organization"] = relationship(back_populates="locations")
    area: Mapped["GeographicArea"] = relationship()
    activity_pricing: Mapped[List["ActivityPricing"]] = relationship(
        back_populates="location",
        cascade="all, delete-orphan",
    )
    activity_schedules: Mapped[List["ActivitySchedule"]] = relationship(
        back_populates="location",
        cascade="all, delete-orphan",
    )
