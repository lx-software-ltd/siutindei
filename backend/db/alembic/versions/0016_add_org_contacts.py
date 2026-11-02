"""Add contact fields to organizations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_add_org_contacts"
down_revision: Union[str, None] = "0015_drop_loc_dist_ctry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add contact fields to organizations."""
    op.add_column(
        "organizations",
        sa.Column("phone_country_code", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("phone_number", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("email", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("whatsapp", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("facebook", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("instagram", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("tiktok", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("twitter", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("little_red_book", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("wechat", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove contact fields from organizations."""
    op.drop_column("organizations", "wechat")
    op.drop_column("organizations", "little_red_book")
    op.drop_column("organizations", "twitter")
    op.drop_column("organizations", "tiktok")
    op.drop_column("organizations", "instagram")
    op.drop_column("organizations", "facebook")
    op.drop_column("organizations", "whatsapp")
    op.drop_column("organizations", "email")
    op.drop_column("organizations", "phone_number")
    op.drop_column("organizations", "phone_country_code")
