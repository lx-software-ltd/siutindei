"""Add an optional venue label to locations.

Revision ID: 0061_location_name
Revises: 0060_pricing_month_year

Seed assessment: no seed change. ``name`` is nullable. Existing
``INSERT INTO locations`` rows omit it and stay valid. No new
table, NOT NULL, check, or foreign key.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0061_location_name"
down_revision: Union[str, None] = "0060_pricing_month_year"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the optional venue label."""
    op.add_column("locations", sa.Column("name", sa.Text(), nullable=True))


def downgrade() -> None:
    """Drop the venue label."""
    op.drop_column("locations", "name")
