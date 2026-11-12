"""Admin-set parent-verified flag on organizations.

Revision ID: 0064_org_parent_verified
Revises: 0063_leaflet_enrich

Seed assessment: no seed change. ``parent_verified`` is NOT NULL with
server default ``false``. Existing ``INSERT INTO organizations`` rows
omit the column and receive ``false``. No new table, check, or foreign
key.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0064_org_parent_verified"
down_revision: Union[str, None] = "0063_leaflet_enrich"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the flag. Every existing organization starts unverified."""
    op.add_column(
        "organizations",
        sa.Column(
            "parent_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Admin-only: parents have verified this organization",
        ),
    )


def downgrade() -> None:
    """Drop the flag."""
    op.drop_column("organizations", "parent_verified")
