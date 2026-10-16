"""Website enrichment runs, proposals, and a monthly budget.

Revision ID: 0055_org_enrichment
Revises: 0054_org_review_reason

Seed assessment: org_enrichment_settings is a singleton inserted here,
not by seed_data.sql. org_enrichment_runs and org_enrichment_proposals
are new and left empty. Existing seed SQL still runs. No seed column,
enum, or foreign key changes.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0055_org_enrichment"
down_revision: Union[str, None] = "0054_org_review_reason"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "org_enrichment_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column("seed_url", sa.Text(), nullable=False),
        sa.Column(
            "pages",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "pages_fetched",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "bytes_fetched",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column(
            "cost_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("input_hash", sa.Text(), nullable=True),
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
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'extracting', 'ready', "
            "'failed', 'render_required')",
            name="org_enrichment_runs_status_check",
        ),
    )
    op.create_index(
        "org_enrichment_runs_active_org_idx",
        "org_enrichment_runs",
        ["org_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'extracting')"),
    )
    op.create_index(
        "org_enrichment_runs_org_idx",
        "org_enrichment_runs",
        ["org_id", "created_at"],
    )
    op.create_table(
        "org_enrichment_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("field", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("current_value", postgresql.JSONB(), nullable=True),
        sa.Column("proposed_value", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column(
            "unverified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("proposed_hash", sa.Text(), nullable=False),
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
            ["run_id"],
            ["org_enrichment_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'applied', 'dismissed', 'superseded')",
            name="org_enrichment_proposals_status_check",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="org_enrichment_proposals_confidence_check",
        ),
    )
    op.create_index(
        "org_enrichment_proposals_run_idx",
        "org_enrichment_proposals",
        ["run_id"],
    )
    op.create_index(
        "org_enrichment_proposals_org_idx",
        "org_enrichment_proposals",
        ["org_id", "status"],
    )
    op.create_table(
        "org_enrichment_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "monthly_cost_limit_usd",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("25"),
        ),
        sa.Column(
            "max_pages",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("6"),
        ),
        sa.Column(
            "max_page_bytes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1000000"),
        ),
        sa.Column(
            "copy_media",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "min_confidence_shown",
            sa.Numeric(4, 3),
            nullable=False,
            server_default=sa.text("0.500"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "id = 1",
            name="org_enrichment_settings_singleton_check",
        ),
        sa.CheckConstraint(
            "monthly_cost_limit_usd > 0 AND monthly_cost_limit_usd <= 1000",
            name="org_enrichment_settings_cost_check",
        ),
        sa.CheckConstraint(
            "max_pages >= 1 AND max_pages <= 8",
            name="org_enrichment_settings_pages_check",
        ),
        sa.CheckConstraint(
            "max_page_bytes >= 10000 AND max_page_bytes <= 2000000",
            name="org_enrichment_settings_bytes_check",
        ),
        sa.CheckConstraint(
            "min_confidence_shown >= 0 AND min_confidence_shown <= 1",
            name="org_enrichment_settings_confidence_check",
        ),
    )
    op.execute("INSERT INTO org_enrichment_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("org_enrichment_settings")
    op.drop_index(
        "org_enrichment_proposals_org_idx",
        table_name="org_enrichment_proposals",
    )
    op.drop_index(
        "org_enrichment_proposals_run_idx",
        table_name="org_enrichment_proposals",
    )
    op.drop_table("org_enrichment_proposals")
    op.drop_index(
        "org_enrichment_runs_org_idx",
        table_name="org_enrichment_runs",
    )
    op.drop_index(
        "org_enrichment_runs_active_org_idx",
        table_name="org_enrichment_runs",
    )
    op.drop_table("org_enrichment_runs")
