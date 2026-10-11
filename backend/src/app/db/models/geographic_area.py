"""Geographic area model."""

from __future__ import annotations

from typing import List, Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GeographicArea(Base):
    """Hierarchical geographic area.

    Hong Kong is country, region, district, then neighbourhood.
    A location stores a leaf: a neighbourhood where those exist.
    """

    __tablename__ = "geographic_areas"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    parent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geographic_areas.id", ondelete="CASCADE"),
        nullable=True,
        comment="NULL for root (country) nodes",
    )
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    name_translations: Mapped[dict[str, str]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Language map for non-English name translations",
    )
    level: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
        comment="country | region | city | district | neighbourhood",
    )
    code: Mapped[Optional[str]] = mapped_column(
        Text(),
        nullable=True,
        comment="ISO 3166-1 alpha-2 for countries (HK, SG, AE)",
    )
    active: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=text("true"),
        comment="Only active countries (and their children) are shown",
    )
    display_order: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        server_default=text("0"),
    )
    lat: Mapped[Optional[float]] = mapped_column(
        Numeric(9, 6),
        nullable=True,
        comment="Centroid latitude for neighbourhood matching",
    )
    lng: Mapped[Optional[float]] = mapped_column(
        Numeric(9, 6),
        nullable=True,
        comment="Centroid longitude for neighbourhood matching",
    )

    parent: Mapped[Optional["GeographicArea"]] = relationship(
        remote_side="GeographicArea.id",
        back_populates="children",
    )
    children: Mapped[List["GeographicArea"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="GeographicArea.display_order",
    )
