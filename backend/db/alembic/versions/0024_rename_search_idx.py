"""Rename activity search composite index."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0024_rename_search_idx"
down_revision: Union[str, None] = "0023_add_org_logo_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename activity search composite index."""
    op.execute(
        "ALTER INDEX IF EXISTS idx_activity_search_composite "
        "RENAME TO idx_search_composite"
    )


def downgrade() -> None:
    """Rename search composite index."""
    op.execute(
        "ALTER INDEX IF EXISTS idx_search_composite "
        "RENAME TO idx_activity_search_composite"
    )
