"""Category suggestion queue, settings, and pending category.

Revision ID: 0034_category_suggestions
Revises: 0033_org_review_status

Seed assessment: new tables only, plus one idempotent activity_categories
lookup row. No existing columns or enums change, so seed_data.sql is
unchanged. The settings singleton is inserted here so every environment
has it without a seed edit.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0034_category_suggestions"
down_revision: Union[str, None] = "0033_org_review_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PENDING_ID = "c1111111-1111-1111-1111-111111111199"
_SETTINGS_ID = "c2222222-2222-2222-2222-222222222201"


def upgrade() -> None:
    """Create suggestion tables and the pending categorisation row."""
    op.create_table(
        "category_suggestion_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "on_import_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "auto_enrich_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("openrouter_model", sa.Text(), nullable=True),
        sa.Column(
            "fallback_models",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "max_evidence_items",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("25"),
        ),
        sa.Column(
            "deny_data_collection",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "max_evidence_items BETWEEN 5 AND 50",
            name="cat_sug_settings_evidence_check",
        ),
    )
    op.create_table(
        "category_suggestions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("requested_name", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'import'"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "enrichment_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
        sa.Column("enrichment_error", sa.Text(), nullable=True),
        sa.Column("enriched_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("suggested_name", sa.Text(), nullable=True),
        sa.Column(
            "name_translations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "suggested_parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activity_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "maps_to_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activity_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "alternatives",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "usage",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activity_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "merged_into_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activity_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column(
            "activity_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("reopened_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
            "source IN ('import', 'scan')",
            name="cat_sug_source_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'merged', 'rejected')",
            name="cat_sug_status_check",
        ),
        sa.CheckConstraint(
            "enrichment_status IN "
            "('none', 'queued', 'running', 'done', 'failed')",
            name="cat_sug_enrich_check",
        ),
        sa.UniqueConstraint("fingerprint", name="cat_sug_fingerprint_key"),
    )
    op.create_index(
        "cat_sug_status_idx",
        "category_suggestions",
        ["status"],
    )
    op.create_index(
        "cat_sug_enrich_idx",
        "category_suggestions",
        ["enrichment_status"],
    )
    op.create_index(
        "cat_sug_created_idx",
        "category_suggestions",
        ["created_at"],
    )
    op.create_table(
        "category_suggestion_activities",
        sa.Column(
            "suggestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("category_suggestions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "activity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "import_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requested_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "cat_sug_act_activity_idx",
        "category_suggestion_activities",
        ["activity_id"],
    )
    op.create_index(
        "cat_sug_act_org_idx",
        "category_suggestion_activities",
        ["org_id"],
    )
    op.create_index(
        "cat_sug_act_job_idx",
        "category_suggestion_activities",
        ["import_job_id"],
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE "
        "ON category_suggestion_settings TO siutindei_admin;"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE "
        "ON category_suggestions TO siutindei_admin;"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE "
        "ON category_suggestion_activities TO siutindei_admin;"
    )
    op.execute("""
        CREATE TRIGGER category_suggestion_settings_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON category_suggestion_settings
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
    """)
    op.execute("""
        CREATE TRIGGER category_suggestions_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON category_suggestions
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
    """)
    op.execute(f"""
        INSERT INTO category_suggestion_settings (id)
        SELECT '{_SETTINGS_ID}'::uuid
        WHERE NOT EXISTS (
            SELECT 1 FROM category_suggestion_settings
            WHERE id = '{_SETTINGS_ID}'::uuid
        );
    """)
    op.execute(f"""
        INSERT INTO activity_categories (
            id, parent_id, name, name_translations, display_order
        )
        SELECT
            '{_PENDING_ID}'::uuid,
            NULL,
            'Pending categorisation',
            '{{"zh": "待分類"}}'::jsonb,
            9999
        WHERE NOT EXISTS (
            SELECT 1 FROM activity_categories
            WHERE id = '{_PENDING_ID}'::uuid
        );
    """)


def downgrade() -> None:
    """Drop suggestion tables and the unused pending category row."""
    op.execute(
        "DROP TRIGGER IF EXISTS category_suggestions_audit_trigger "
        "ON category_suggestions;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS category_suggestion_settings_audit_trigger "
        "ON category_suggestion_settings;"
    )
    op.drop_index(
        "cat_sug_act_job_idx",
        table_name="category_suggestion_activities",
    )
    op.drop_index(
        "cat_sug_act_org_idx",
        table_name="category_suggestion_activities",
    )
    op.drop_index(
        "cat_sug_act_activity_idx",
        table_name="category_suggestion_activities",
    )
    op.drop_table("category_suggestion_activities")
    op.drop_index("cat_sug_created_idx", table_name="category_suggestions")
    op.drop_index("cat_sug_enrich_idx", table_name="category_suggestions")
    op.drop_index("cat_sug_status_idx", table_name="category_suggestions")
    op.drop_table("category_suggestions")
    op.drop_table("category_suggestion_settings")
    op.execute(f"""
        DELETE FROM activity_categories
        WHERE id = '{_PENDING_ID}'::uuid
          AND NOT EXISTS (
            SELECT 1 FROM activities
            WHERE category_id = '{_PENDING_ID}'::uuid
          );
    """)
