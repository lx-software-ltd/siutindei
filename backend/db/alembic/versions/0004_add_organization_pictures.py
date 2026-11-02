"""Add picture URLs column for organizations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_add_organization_pictures"
down_revision: Union[str, None] = "0003_add_admin_db_user"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add picture URLs array to organizations."""
    op.add_column(
        "organizations",
        sa.Column(
            "picture_urls",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )


def downgrade() -> None:
    """Remove picture URLs array from organizations."""
    op.drop_column("organizations", "picture_urls")
