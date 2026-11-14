"""Activity category model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.activity import Activity


class ActivityCategory(Base):
    """Hierarchical activity category."""

    __tablename__ = "activity_categories"
    __table_args__ = (
        UniqueConstraint(
            "parent_id",
            "name",
            name="uq_activity_category_parent_name",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    parent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activity_categories.id", ondelete="RESTRICT"),
        nullable=True,
        comment="NULL for root category nodes",
    )
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    name_translations: Mapped[dict[str, str]] = mapped_column(
        JSONB(),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Language map for non-English name translations",
    )
    display_order: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        server_default=text("0"),
    )
    show_in_wizard: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    hidden_from_public: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Public search leaves out this category and its descendants",
    )

    parent: Mapped[ActivityCategory | None] = relationship(
        remote_side="ActivityCategory.id",
        back_populates="children",
    )
    children: Mapped[list[ActivityCategory]] = relationship(
        back_populates="parent",
        order_by="ActivityCategory.display_order",
    )
    activities: Mapped[list[Activity]] = relationship(
        back_populates="category",
    )
