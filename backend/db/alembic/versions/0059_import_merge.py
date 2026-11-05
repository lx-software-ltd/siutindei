"""Baselines and per-field proposals for catalog imports.

Revision ID: 0059_import_merge
Revises: 0058_entry_order_idx

Seed assessment: two new tables start empty. ``seed_data.sql`` does not
change. ``import_settings`` gains two columns with server defaults, so
the existing singleton row stays valid. No new NOT NULL without a
default, no renamed or dropped seed column, no enum change in seed
rows, and no new foreign key.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0059_import_merge"
down_revision: Union[str, None] = "0058_entry_order_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY = (
    "entity_type IN ('organization', 'location', 'activity', 'pricing', 'schedule')"
)


def upgrade() -> None:
    """Store what the source last said, and queue fields both sides changed."""
    op.create_table(
        "import_baselines",
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.PrimaryKeyConstraint(
            "entity_type", "entity_id", name="import_baselines_pkey"
        ),
        sa.CheckConstraint(_ENTITY, name="import_baselines_entity_type_check"),
    )
    op.execute(
        """
        CREATE INDEX import_baselines_org_name_idx
        ON import_baselines (org_id, lower(trim(payload->>'name')))
        """
    )
    op.execute(
        """
        CREATE INDEX import_baselines_org_address_idx
        ON import_baselines (org_id, lower(trim(payload->>'address')))
        """
    )
    op.create_table(
        "import_change_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("base_value", postgresql.JSONB(), nullable=True),
        sa.Column("current_value", postgresql.JSONB(), nullable=True),
        sa.Column("proposed_value", postgresql.JSONB(), nullable=True),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
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
        sa.CheckConstraint(_ENTITY, name="import_change_proposals_entity_type_check"),
        sa.CheckConstraint(
            "status IN ('pending', 'applied', 'dismissed')",
            name="import_change_proposals_status_check",
        ),
    )
    op.create_index(
        "import_change_proposals_org_idx",
        "import_change_proposals",
        ["org_id", "status"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX import_change_proposals_pending_idx
        ON import_change_proposals (entity_type, entity_id, field)
        WHERE status = 'pending'
        """
    )
    op.add_column(
        "import_settings",
        sa.Column(
            "existing_rows",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'merge'"),
        ),
    )
    op.add_column(
        "import_settings",
        sa.Column(
            "approved_organizations",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'propose'"),
        ),
    )
    op.create_check_constraint(
        "import_settings_existing_rows_check",
        "import_settings",
        "existing_rows IN ('apply', 'merge', 'propose')",
    )
    op.create_check_constraint(
        "import_settings_approved_orgs_check",
        "import_settings",
        "approved_organizations IN ('merge', 'propose')",
    )
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON import_baselines, import_change_proposals
        TO siutindei_admin
        """
    )


def downgrade() -> None:
    """Drop the merge tables and the two import settings columns."""
    op.drop_constraint(
        "import_settings_approved_orgs_check",
        "import_settings",
        type_="check",
    )
    op.drop_constraint(
        "import_settings_existing_rows_check",
        "import_settings",
        type_="check",
    )
    op.drop_column("import_settings", "approved_organizations")
    op.drop_column("import_settings", "existing_rows")
    op.execute("DROP INDEX IF EXISTS import_change_proposals_pending_idx")
    op.drop_index(
        "import_change_proposals_org_idx",
        table_name="import_change_proposals",
    )
    op.drop_table("import_change_proposals")
    op.execute("DROP INDEX IF EXISTS import_baselines_org_address_idx")
    op.execute("DROP INDEX IF EXISTS import_baselines_org_name_idx")
    op.drop_table("import_baselines")
