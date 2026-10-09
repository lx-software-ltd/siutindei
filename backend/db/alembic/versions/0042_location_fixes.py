"""Location sweeps, venue proposals, and a separate model budget.

Revision ID: 0042_location_fixes
Revises: 0041_data_quality

Seed assessment: location_scan_runs and location_fix_proposals are new
and left empty. location_fix_settings is a singleton inserted here, not
by seed_data.sql. No seed column, enum, or foreign key changes.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042_location_fixes"
down_revision: Union[str, None] = "0041_data_quality"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "location_scan_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_scope", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column(
            "total_entities",
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
            "created_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "skipped_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cleared_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "auto_applied_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "queued_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "failed_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cost_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "truncated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')",
            name="location_scan_status_check",
        ),
        sa.CheckConstraint(
            "review_scope IN ('pending_review', 'all')",
            name="location_scan_scope_check",
        ),
        sa.CheckConstraint(
            "entity_type IS NULL OR entity_type IN ('organization', 'activity')",
            name="location_scan_entity_check",
        ),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX location_scan_one_active
        ON location_scan_runs ((true))
        WHERE status IN ('queued', 'running')
        """
    )
    op.create_table(
        "location_fix_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "target_location_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("proposed_location", postgresql.JSONB(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_location_id"],
            ["locations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["scan_run_id"],
            ["location_scan_runs.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "entity_type IN ('organization', 'activity')",
            name="location_fix_entity_type_check",
        ),
        sa.CheckConstraint(
            "kind IN ('link_existing', 'create_location', 'unresolved')",
            name="location_fix_kind_check",
        ),
        sa.CheckConstraint(
            "source IN ("
            "'rule:single_location', 'rule:pricing_schedule', "
            "'rule:name_area', 'rule:no_venue', 'model')",
            name="location_fix_source_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'applied', 'dismissed')",
            name="location_fix_status_check",
        ),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX location_fix_one_pending
        ON location_fix_proposals (entity_type, entity_id)
        WHERE status = 'pending'
        """
    )
    op.create_index(
        "location_fix_org_idx",
        "location_fix_proposals",
        ["org_id", "status"],
    )
    op.create_table(
        "location_fix_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "monthly_cost_limit_usd",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("50"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id = 1", name="location_fix_settings_singleton_check"),
        sa.CheckConstraint(
            "monthly_cost_limit_usd > 0 AND monthly_cost_limit_usd <= 1000",
            name="location_fix_settings_cost_check",
        ),
    )
    op.execute(
        """
        INSERT INTO location_fix_settings (id, monthly_cost_limit_usd)
        VALUES (1, 50)
        """
    )


def downgrade() -> None:
    op.drop_table("location_fix_settings")
    op.drop_index("location_fix_org_idx", table_name="location_fix_proposals")
    op.execute("DROP INDEX IF EXISTS location_fix_one_pending")
    op.drop_table("location_fix_proposals")
    op.execute("DROP INDEX IF EXISTS location_scan_one_active")
    op.drop_table("location_scan_runs")
