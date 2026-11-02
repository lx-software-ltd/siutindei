"""Rename picture_urls to media_urls in organizations table."""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0006_rename_to_media_urls"
down_revision: Union[str, None] = "0005_add_organization_owner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename picture_urls column to media_urls."""
    op.alter_column(
        "organizations",
        "picture_urls",
        new_column_name="media_urls",
    )


def downgrade() -> None:
    """Rename media_urls column back to picture_urls."""
    op.alter_column(
        "organizations",
        "media_urls",
        new_column_name="picture_urls",
    )
