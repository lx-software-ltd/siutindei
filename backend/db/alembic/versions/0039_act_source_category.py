"""Keep imported category labels and wizard visibility.

Revision ID: 0039_act_source_category
Revises: 0038_capture_default_on

Seed assessment: source_category_name is nullable. The backfill copies
requested_name only from import-sourced suggestion links. show_in_wizard
and scan mode/labels have server defaults. seed_data.sql inserts Sport
only and does not insert scan runs, so existing seed rows stay valid.
The four wizard categories are flagged when present.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0039_act_source_category"
down_revision: Union[str, None] = "0038_capture_default_on"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WIZARD_IDS = (
    "c1111111-1111-1111-1111-111111111101",
    "c1111111-1111-1111-1111-111111111102",
    "c1111111-1111-1111-1111-111111111103",
    "c1111111-1111-1111-1111-111111111104",
)


def upgrade() -> None:
    """Store source labels, scan mode, and wizard flags."""
    op.add_column(
        "activities",
        sa.Column("source_category_name", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE activities AS activity SET source_category_name = picked.name "
        "FROM ("
        "  SELECT DISTINCT ON (link.activity_id) "
        "    link.activity_id, link.requested_name AS name "
        "  FROM category_suggestion_activities AS link "
        "  JOIN category_suggestions AS suggestion "
        "    ON suggestion.id = link.suggestion_id "
        "  WHERE suggestion.source = 'import' "
        "  ORDER BY link.activity_id, link.created_at DESC"
        ") AS picked "
        "WHERE activity.id = picked.activity_id "
        "AND activity.source_category_name IS NULL"
    )
    op.add_column(
        "category_scan_runs",
        sa.Column(
            "mode",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'verify'"),
        ),
    )
    op.add_column(
        "category_scan_runs",
        sa.Column(
            "labels_total",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "cat_scan_run_mode_check",
        "category_scan_runs",
        "mode IN ('verify', 'discover')",
    )
    op.add_column(
        "activity_categories",
        sa.Column(
            "show_in_wizard",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    ids = ", ".join(f"'{item}'" for item in _WIZARD_IDS)
    op.execute(
        "UPDATE activity_categories SET show_in_wizard = true " f"WHERE id IN ({ids})"
    )


def downgrade() -> None:
    """Remove source labels, scan mode, and wizard flags."""
    op.drop_column("activity_categories", "show_in_wizard")
    op.drop_constraint(
        "cat_scan_run_mode_check",
        "category_scan_runs",
        type_="check",
    )
    op.drop_column("category_scan_runs", "labels_total")
    op.drop_column("category_scan_runs", "mode")
    op.drop_column("activities", "source_category_name")
