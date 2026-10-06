"""Category-check monthly cost cap and one active run.

Revision ID: 0037_scan_cost_cap
Revises: 0036_category_scan

Seed assessment: one NOT NULL settings column with server default 25.
seed_data.sql does not insert category_suggestion_settings. The
partial unique index adds no rows. Existing seed data is unchanged.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0037_scan_cost_cap"
down_revision: Union[str, None] = "0036_category_scan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cap monthly category-check spend and allow one active run."""
    op.add_column(
        "category_suggestion_settings",
        sa.Column(
            "monthly_cost_limit_usd",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("25"),
        ),
    )
    op.create_check_constraint(
        "cat_sug_settings_cost_check",
        "category_suggestion_settings",
        "monthly_cost_limit_usd > 0 AND monthly_cost_limit_usd <= 1000",
    )
    op.execute(
        "CREATE UNIQUE INDEX cat_scan_one_active "
        "ON category_scan_runs ((true)) "
        "WHERE status IN ('queued', 'running')"
    )


def downgrade() -> None:
    """Remove the cost cap and the single-active-run index."""
    op.execute("DROP INDEX IF EXISTS cat_scan_one_active")
    op.drop_constraint(
        "cat_sug_settings_cost_check",
        "category_suggestion_settings",
        type_="check",
    )
    op.drop_column("category_suggestion_settings", "monthly_cost_limit_usd")
