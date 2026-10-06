"""Turn category capture on for new and existing settings.

Revision ID: 0038_capture_default_on
Revises: 0037_scan_cost_cap

Seed assessment: updates the settings singleton and its server default.
seed_data.sql does not insert category_suggestion_settings, so it is
unchanged.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0038_capture_default_on"
down_revision: Union[str, None] = "0037_scan_cost_cap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Capture unknown import category names unless an admin turns it off."""
    op.alter_column(
        "category_suggestion_settings",
        "on_import_enabled",
        server_default=sa.text("true"),
    )
    op.execute("UPDATE category_suggestion_settings SET on_import_enabled = true")


def downgrade() -> None:
    """Restore capture-off as the settings default."""
    op.execute("UPDATE category_suggestion_settings SET on_import_enabled = false")
    op.alter_column(
        "category_suggestion_settings",
        "on_import_enabled",
        server_default=sa.text("false"),
    )
