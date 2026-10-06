"""Category-check runs, reviews, and auto-assign threshold.

Revision ID: 0036_category_scan
Revises: 0035_org_source_fields

Seed assessment: two new tables and one nullable settings column with
server default 0.900. seed_data.sql does not insert
category_suggestion_settings (the singleton is created by migration
0034 and by get_or_create). No existing seed rows change.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0036_category_scan"
down_revision: Union[str, None] = "0035_org_source_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add category-check storage and the auto-assign threshold."""
    op.add_column(
        "category_suggestion_settings",
        sa.Column(
            "auto_assign_threshold",
            sa.Numeric(4, 3),
            nullable=True,
            server_default=sa.text("0.900"),
        ),
    )
    op.create_check_constraint(
        "cat_sug_settings_threshold_check",
        "category_suggestion_settings",
        "auto_assign_threshold IS NULL OR "
        "(auto_assign_threshold >= 0.5 AND auto_assign_threshold <= 1)",
    )
    op.create_table(
        "category_scan_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column(
            "total_activities",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "batches_total",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "batches_done",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "confirmed", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "auto_applied",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "reassign_pending",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "proposed", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "cost_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "processed_message_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')",
            name="cat_scan_run_status_check",
        ),
    )
    op.create_index("cat_scan_runs_status_idx", "category_scan_runs", ["status"])
    op.create_table(
        "activity_category_reviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scan_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("category_scan_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "activity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "current_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activity_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column(
            "proposed_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activity_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "suggestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("category_suggestions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "previous_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activity_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "verdict IN ('confirm', 'reassign', 'propose')",
            name="activity_cat_reviews_verdict_check",
        ),
        sa.CheckConstraint(
            "status IN ('confirmed', 'pending', 'auto_applied', 'applied', "
            "'dismissed', 'reverted')",
            name="activity_cat_reviews_status_check",
        ),
        sa.UniqueConstraint(
            "scan_run_id",
            "activity_id",
            name="activity_cat_reviews_run_activity_key",
        ),
    )
    op.create_index(
        "activity_cat_reviews_activity_idx",
        "activity_category_reviews",
        ["activity_id", "created_at"],
    )
    op.create_index(
        "activity_cat_reviews_status_idx",
        "activity_category_reviews",
        ["status"],
    )
    op.create_index(
        "activity_cat_reviews_run_idx",
        "activity_category_reviews",
        ["scan_run_id"],
    )


def downgrade() -> None:
    """Remove category-check storage and the threshold column."""
    op.drop_index(
        "activity_cat_reviews_run_idx", table_name="activity_category_reviews"
    )
    op.drop_index(
        "activity_cat_reviews_status_idx", table_name="activity_category_reviews"
    )
    op.drop_index(
        "activity_cat_reviews_activity_idx", table_name="activity_category_reviews"
    )
    op.drop_table("activity_category_reviews")
    op.drop_index("cat_scan_runs_status_idx", table_name="category_scan_runs")
    op.drop_table("category_scan_runs")
    op.drop_constraint(
        "cat_sug_settings_threshold_check",
        "category_suggestion_settings",
        type_="check",
    )
    op.drop_column("category_suggestion_settings", "auto_assign_threshold")
