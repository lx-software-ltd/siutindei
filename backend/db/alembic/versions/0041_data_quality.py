"""Duplicate matching, merge forwarding, and name-fix proposals.

Revision ID: 0041_data_quality
Revises: 0040_recheck_taxonomy

Seed assessment: organizations.name_key is nullable and filled by a
BEFORE INSERT trigger, so seed inserts that omit the column stay valid.
organization_merges, organization_duplicate_dismissals, and
name_fix_proposals are new and empty. name_fix_settings is a singleton
inserted here, not by seed_data.sql. No seed column, enum, or FK used
by existing seed rows changes.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0041_data_quality"
down_revision: Union[str, None] = "0040_recheck_taxonomy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NAME_KEY_FN = """
CREATE OR REPLACE FUNCTION organizations_name_key(raw text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT regexp_replace(
    lower(regexp_replace(coalesce(raw, ''), '[^[:alnum:]]+', '', 'g')),
    '(limited|ltd|company|inc|llc|有限公司)$',
    ''
  );
$$;
"""

_NAME_KEY_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION organizations_set_name_key()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.name_key := organizations_name_key(NEW.name);
  RETURN NEW;
END;
$$;
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column(
        "organizations",
        sa.Column("name_key", sa.Text(), nullable=True),
    )
    op.execute(_NAME_KEY_FN)
    op.execute(_NAME_KEY_TRIGGER_FN)
    op.execute(
        """
        CREATE TRIGGER organizations_name_key_trg
        BEFORE INSERT OR UPDATE OF name ON organizations
        FOR EACH ROW EXECUTE FUNCTION organizations_set_name_key()
        """
    )
    op.execute("UPDATE organizations SET name_key = organizations_name_key(name)")
    op.create_index(
        "organizations_name_key_idx",
        "organizations",
        ["name_key"],
    )
    op.execute(
        """
        CREATE INDEX organizations_name_trgm_idx
        ON organizations USING gin (lower(name) gin_trgm_ops)
        """
    )

    op.create_table(
        "organization_merges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merged_org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("survivor_org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("place_id", sa.Text(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "moved_counts",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("merged_by", sa.Text(), nullable=True),
        sa.Column(
            "merged_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["survivor_org_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "organization_merges_source_id_idx",
        "organization_merges",
        ["source_id"],
    )
    op.create_index(
        "organization_merges_place_id_idx",
        "organization_merges",
        ["place_id"],
    )
    op.create_index(
        "organization_merges_survivor_idx",
        "organization_merges",
        ["survivor_org_id"],
    )

    op.create_table(
        "organization_duplicate_dismissals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id_low", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id_high", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dismissed_by", sa.Text(), nullable=True),
        sa.Column(
            "dismissed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id_low"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id_high"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "org_id_low",
            "org_id_high",
            name="org_dup_dismissals_pair_key",
        ),
        sa.CheckConstraint(
            "org_id_low <> org_id_high",
            name="org_dup_dismissals_distinct_check",
        ),
    )

    op.create_table(
        "name_fix_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "field",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'name'"),
        ),
        sa.Column("current_value", sa.Text(), nullable=False),
        sa.Column("proposed_value", sa.Text(), nullable=False),
        sa.Column("rules", postgresql.JSONB(), nullable=False),
        sa.Column("translation_patch", postgresql.JSONB(), nullable=True),
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
        sa.CheckConstraint(
            "entity_type IN ('organization', 'activity')",
            name="name_fix_entity_type_check",
        ),
        sa.CheckConstraint("field = 'name'", name="name_fix_field_check"),
        sa.CheckConstraint(
            "status IN ('pending', 'applied', 'dismissed')",
            name="name_fix_status_check",
        ),
    )
    op.create_index(
        "name_fix_proposals_status_idx",
        "name_fix_proposals",
        ["status", "entity_type"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX name_fix_pending_entity_field
        ON name_fix_proposals (entity_type, entity_id, field)
        WHERE status = 'pending'
        """
    )

    op.create_table(
        "name_fix_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled_rules", postgresql.JSONB(), nullable=False),
        sa.Column("exception_words", postgresql.JSONB(), nullable=False),
        sa.Column("bracket_suffixes", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id = 1", name="name_fix_settings_singleton_check"),
    )
    op.execute(
        """
        INSERT INTO name_fix_settings (
          id, enabled_rules, exception_words, bracket_suffixes
        ) VALUES (
          1,
          '["html_entities","nfkc","whitespace","trailing_punctuation",
            "cjk_spacing","title_case","brackets","split_bilingual"]'::jsonb,
          '["YMCA","HK","LCSD","EDB","SWD","NGO","STEM","AI","IT","UK","US",
            "HKD"]'::jsonb,
          '["lcsd","edb","swd"]'::jsonb
        )
        """
    )


def downgrade() -> None:
    op.drop_table("name_fix_settings")
    op.execute("DROP INDEX IF EXISTS name_fix_pending_entity_field")
    op.drop_index("name_fix_proposals_status_idx", table_name="name_fix_proposals")
    op.drop_table("name_fix_proposals")
    op.drop_table("organization_duplicate_dismissals")
    op.drop_index(
        "organization_merges_survivor_idx",
        table_name="organization_merges",
    )
    op.drop_index(
        "organization_merges_place_id_idx",
        table_name="organization_merges",
    )
    op.drop_index(
        "organization_merges_source_id_idx",
        table_name="organization_merges",
    )
    op.drop_table("organization_merges")
    op.execute("DROP INDEX IF EXISTS organizations_name_trgm_idx")
    op.drop_index("organizations_name_key_idx", table_name="organizations")
    op.execute("DROP TRIGGER IF EXISTS organizations_name_key_trg ON organizations")
    op.execute("DROP FUNCTION IF EXISTS organizations_set_name_key()")
    op.execute("DROP FUNCTION IF EXISTS organizations_name_key(text)")
    op.drop_column("organizations", "name_key")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
