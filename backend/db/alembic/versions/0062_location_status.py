"""Add open or closed status to locations.

Revision ID: 0062_location_status
Revises: 0061_location_name

Seed assessment: no seed change. ``status`` is NOT NULL with server
default ``open``. Existing ``INSERT INTO locations`` rows omit the
column and receive ``open``. The check accepts that default. No new
table or foreign key.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0062_location_status"
down_revision: Union[str, None] = "0061_location_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUS_VALUES = ("open", "temporarily_closed", "permanently_closed")


def upgrade() -> None:
    """Add the venue open/closed status. Existing rows are open."""
    op.add_column(
        "locations",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="open",
        ),
    )
    op.create_check_constraint(
        "locations_status_check",
        "locations",
        "status IN (" + ", ".join(f"'{value}'" for value in _STATUS_VALUES) + ")",
    )


def downgrade() -> None:
    """Drop the venue open/closed status."""
    op.drop_constraint("locations_status_check", "locations", type_="check")
    op.drop_column("locations", "status")
