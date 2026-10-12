"""Version organizations and the records that describe them.

Revision ID: 0047_catalog_versions
Revises: 0046_deleted_org_import

Seed assessment: ``version`` and ``media_version`` are NOT NULL with
server default 1. seed_data.sql omits both columns and stays valid.
``catalog_versions`` is not seeded; the triggers fill it when the seed
inserts organizations. No seed column is renamed or dropped, and no
enum used by seed rows changes. The backfill may insert
``organization_merges`` rows with ``kind = 'delete'`` for organizations
already removed. Those rows are empty on a fresh database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0047_catalog_versions"
down_revision: Union[str, None] = "0046_deleted_org_import"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DB = Path(__file__).resolve().parents[2]
_VERSIONED = (
    "organizations",
    "locations",
    "activities",
    "activity_pricing",
    "activity_schedule",
)


def upgrade() -> None:
    """Add version columns, history, and the bump triggers."""
    for table in _VERSIONED:
        op.add_column(
            table,
            sa.Column(
                "version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
        )
    op.add_column(
        "organizations",
        sa.Column(
            "media_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_table(
        "catalog_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("changed_fields", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("txid", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("related_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "entity_type IN ('organization', 'media', 'location', "
            "'activity', 'pricing', 'schedule')",
            name="catalog_versions_entity_type_check",
        ),
        sa.CheckConstraint(
            "action IN ('created', 'updated', 'deleted')",
            name="catalog_versions_action_check",
        ),
        sa.CheckConstraint("version > 0", name="catalog_versions_version_check"),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "version",
            name="catalog_versions_entity_version_key",
        ),
    )
    op.create_index(
        "catalog_versions_org_created_idx",
        "catalog_versions",
        ["org_id", "created_at"],
    )
    op.create_index(
        "catalog_versions_txid_idx",
        "catalog_versions",
        ["txid", "entity_type", "org_id"],
    )
    op.execute((_DB / "catalog_version_triggers.sql").read_text(encoding="utf-8"))
    # Backfill updates version columns. Replica role skips the bump
    # triggers so that update does not write a second history row.
    op.execute("SET session_replication_role = replica")
    op.execute((_DB / "catalog_version_backfill.sql").read_text(encoding="utf-8"))
    op.execute("SET session_replication_role = origin")
    op.execute("GRANT SELECT, INSERT, UPDATE ON catalog_versions TO siutindei_app;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON catalog_versions TO siutindei_admin;")


def downgrade() -> None:
    """Drop version history. Catalog rows keep their current values."""
    for name, table in (
        ("activity_schedule_entries_version_touch", "activity_schedule_entries"),
        ("activity_locations_version_touch", "activity_locations"),
        ("activity_schedule_version_record", "activity_schedule"),
        ("activity_schedule_version_bump", "activity_schedule"),
        ("activity_pricing_version_record", "activity_pricing"),
        ("activity_pricing_version_bump", "activity_pricing"),
        ("activities_version_record", "activities"),
        ("activities_version_bump", "activities"),
        ("locations_version_record", "locations"),
        ("locations_version_bump", "locations"),
        ("organizations_version_record", "organizations"),
        ("organizations_version_bump", "organizations"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {name} ON {table}")
    for function in (
        "catalog_entry_touch()",
        "catalog_join_touch()",
        "catalog_version_record()",
        "catalog_version_bump()",
        "catalog_note_child(text, uuid)",
        "catalog_rewrite_open_snapshot(text, uuid)",
        "catalog_upsert_version(text, uuid, uuid, integer, text, jsonb, text[], text)",
        "catalog_org_id(text, jsonb)",
        "catalog_version_reason()",
        "catalog_import_job_id()",
        "catalog_enrich_snapshot(text, jsonb)",
        "catalog_audit_differs(jsonb, jsonb)",
        "catalog_changed_fields(jsonb, jsonb)",
        "catalog_tracked(jsonb)",
        "catalog_entity_type(text)",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}")
    op.drop_index("catalog_versions_txid_idx", table_name="catalog_versions")
    op.drop_index("catalog_versions_org_created_idx", table_name="catalog_versions")
    op.drop_table("catalog_versions")
    op.drop_column("organizations", "media_version")
    for table in _VERSIONED:
        op.drop_column(table, "version")
