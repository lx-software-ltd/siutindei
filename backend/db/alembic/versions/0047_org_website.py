"""Add organizations.website.

Seed assessment: website is nullable. seed_data.sql inserts omit the
column and still run. No seed rows change.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047_org_website"
down_revision: Union[str, None] = "0046_deleted_org_import"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the organization website column."""
    op.add_column(
        "organizations",
        sa.Column(
            "website",
            sa.Text(),
            nullable=True,
            comment="Organization website",
        ),
    )


def downgrade() -> None:
    """Remove the organization website column."""
    op.drop_column("organizations", "website")
