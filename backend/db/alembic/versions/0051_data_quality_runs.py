"""Store import settings and data-quality runs.

Revision ID: 0051_data_quality_runs
Revises: 0050_import_job_source

Seed assessment: ``seed_data.sql`` does not insert these tables.
``import_settings`` is inserted here, including the current
``on_import_enabled`` value when that row exists. Existing seed SQL
still runs. New NOT NULL columns on new tables have values in this
INSERT. No seed column is renamed or dropped. New tables that seed
does not fill are ``data_quality_runs``, ``model_answers``, and
``lookup_answers``. No seed foreign key changes.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0051_data_quality_runs"
down_revision: Union[str, None] = "0050_import_job_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add settings, runs, recorded answers, and check fingerprints."""
    op.create_table(
        "import_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "skip_deleted_organizations",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "name_cleanup",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'apply'"),
        ),
        sa.Column(
            "unknown_categories",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'capture'"),
        ),
        sa.Column(
            "duplicates",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'off'"),
        ),
        sa.Column(
            "locations",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'off'"),
        ),
        sa.Column(
            "categories",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'off'"),
        ),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id = 1", name="import_settings_singleton_check"),
        sa.CheckConstraint(
            "name_cleanup IN ('off', 'propose', 'apply')",
            name="import_settings_name_cleanup_check",
        ),
        sa.CheckConstraint(
            "unknown_categories IN ('capture', 'fail')",
            name="import_settings_unknown_categories_check",
        ),
        sa.CheckConstraint(
            "duplicates IN ('off', 'report')",
            name="import_settings_duplicates_check",
        ),
        sa.CheckConstraint(
            "locations IN ('off', 'check')",
            name="import_settings_locations_check",
        ),
        sa.CheckConstraint(
            "categories IN ('off', 'check')",
            name="import_settings_categories_check",
        ),
    )
    op.execute(
        """
        INSERT INTO import_settings (
            id, skip_deleted_organizations, name_cleanup, unknown_categories,
            duplicates, locations, categories
        )
        SELECT
            1,
            true,
            'apply',
            CASE
                WHEN EXISTS (
                    SELECT 1 FROM category_suggestion_settings
                    WHERE on_import_enabled IS FALSE
                ) THEN 'fail'
                ELSE 'capture'
            END,
            'off',
            'off',
            'off'
        WHERE NOT EXISTS (SELECT 1 FROM import_settings WHERE id = 1)
        """
    )
    op.execute(
        """
        CREATE TRIGGER import_settings_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON import_settings
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
        """
    )
    op.create_table(
        "data_quality_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column(
            "import_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column(
            "scope",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "checks",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "attempt",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "refresh",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column(
            "check_versions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column(
            "processed_message_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "as_of",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "trigger IN ('import', 'manual')",
            name="data_quality_runs_trigger_check",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'partial', 'failed', 'busy')",
            name="data_quality_runs_status_check",
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name="data_quality_runs_idempotency_key",
        ),
    )
    op.create_index(
        "data_quality_runs_import_job_idx",
        "data_quality_runs",
        ["import_job_id", "attempt"],
        unique=True,
        postgresql_where=sa.text("import_job_id IS NOT NULL"),
    )
    op.create_index(
        "data_quality_runs_created_idx",
        "data_quality_runs",
        ["created_at", "id"],
    )
    op.create_table(
        "model_answers",
        sa.Column("key_hash", sa.Text(), primary_key=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column("usage", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "lookup_answers",
        sa.Column("key_hash", sa.Text(), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    for table in (
        "name_fix_proposals",
        "location_fix_proposals",
        "activity_category_reviews",
    ):
        op.add_column(table, sa.Column("input_hash", sa.Text(), nullable=True))
        op.create_index(f"{table}_input_hash_idx", table, ["input_hash"])
    op.add_column(
        "location_scan_runs",
        sa.Column(
            "data_quality_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_quality_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "category_scan_runs",
        sa.Column(
            "data_quality_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_quality_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "location_scan_runs_dq_run_idx",
        "location_scan_runs",
        ["data_quality_run_id"],
        unique=True,
        postgresql_where=sa.text("data_quality_run_id IS NOT NULL"),
    )
    op.create_index(
        "category_scan_runs_dq_run_idx",
        "category_scan_runs",
        ["data_quality_run_id"],
        unique=True,
        postgresql_where=sa.text("data_quality_run_id IS NOT NULL"),
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id, row_number() OVER (
                PARTITION BY activity_id
                ORDER BY created_at DESC, id DESC
            ) AS n
            FROM activity_category_reviews
            WHERE status = 'pending'
        )
        UPDATE activity_category_reviews
        SET status = 'dismissed',
            decided_by = 'migration',
            decided_at = now()
        WHERE id IN (SELECT id FROM ranked WHERE n > 1)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX activity_cat_reviews_one_pending
        ON activity_category_reviews (activity_id)
        WHERE status = 'pending'
        """
    )


def downgrade() -> None:
    """Drop the data-quality run tables and fingerprint columns."""
    op.execute("DROP INDEX IF EXISTS activity_cat_reviews_one_pending")
    op.drop_index("category_scan_runs_dq_run_idx", table_name="category_scan_runs")
    op.drop_index("location_scan_runs_dq_run_idx", table_name="location_scan_runs")
    op.drop_column("category_scan_runs", "data_quality_run_id")
    op.drop_column("location_scan_runs", "data_quality_run_id")
    for table in (
        "activity_category_reviews",
        "location_fix_proposals",
        "name_fix_proposals",
    ):
        op.drop_index(f"{table}_input_hash_idx", table_name=table)
        op.drop_column(table, "input_hash")
    op.drop_table("lookup_answers")
    op.drop_table("model_answers")
    op.drop_index("data_quality_runs_created_idx", table_name="data_quality_runs")
    op.drop_index("data_quality_runs_import_job_idx", table_name="data_quality_runs")
    op.drop_table("data_quality_runs")
    op.execute(
        "DROP TRIGGER IF EXISTS import_settings_audit_trigger ON import_settings;"
    )
    op.drop_table("import_settings")
