"""Rename little_red_book to xiaohongshu."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0017_rename_org_xiaohongshu"
down_revision: Union[str, None] = "0016_add_org_contacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename little_red_book to xiaohongshu."""
    op.alter_column(
        "organizations",
        "little_red_book",
        new_column_name="xiaohongshu",
    )


def downgrade() -> None:
    """Rename xiaohongshu back to little_red_book."""
    op.alter_column(
        "organizations",
        "xiaohongshu",
        new_column_name="little_red_book",
    )
