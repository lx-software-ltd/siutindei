"""Add activity categories and assign activities.

Creates a hierarchical activity_categories table for admin-managed
category trees and adds a required category_id on activities.
Seeds a default "Sport" category and backfills existing activities.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_add_activity_categories"
down_revision: Union[str, None] = "0017_rename_org_xiaohongshu"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPORT_CATEGORY_ID = "99999999-9999-9999-9999-999999999999"


def upgrade() -> None:
    """Create activity_categories and link activities."""
    op.create_table(
        "activity_categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activity_categories.id", ondelete="RESTRICT"),
            nullable=True,
            comment="NULL for root category nodes",
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint(
            "parent_id",
            "name",
            name="uq_activity_category_parent_name",
        ),
    )

    op.create_index(
        "activity_categories_parent_idx",
        "activity_categories",
        ["parent_id"],
    )
    op.create_index(
        "activity_categories_name_idx",
        "activity_categories",
        ["name"],
    )

    op.execute("GRANT SELECT ON activity_categories TO siutindei_app;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON activity_categories "
        "TO siutindei_admin;"
    )

    op.execute("""
        CREATE TRIGGER activity_categories_audit_trigger
        AFTER INSERT OR UPDATE OR DELETE ON activity_categories
        FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
    """)

    category_table = sa.table(
        "activity_categories",
        sa.column("id", postgresql.UUID),
        sa.column("parent_id", postgresql.UUID),
        sa.column("name", sa.Text),
        sa.column("display_order", sa.Integer),
    )
    op.bulk_insert(
        category_table,
        [
            {
                "id": SPORT_CATEGORY_ID,
                "parent_id": None,
                "name": "Sport",
                "display_order": 1,
            }
        ],
    )

    op.add_column(
        "activities",
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="FK to activity_categories",
        ),
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE activities SET category_id = :category_id "
            "WHERE category_id IS NULL;"
        ),
        {"category_id": SPORT_CATEGORY_ID},
    )

    op.alter_column("activities", "category_id", nullable=False)
    op.create_foreign_key(
        "fk_activities_category_id",
        "activities",
        "activity_categories",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("activities_category_idx", "activities", ["category_id"])


def downgrade() -> None:
    """Remove activity categories and category_id from activities."""
    op.drop_index("activities_category_idx", table_name="activities")
    op.drop_constraint("fk_activities_category_id", "activities", type_="foreignkey")
    op.drop_column("activities", "category_id")

    op.execute(
        "DROP TRIGGER IF EXISTS activity_categories_audit_trigger "
        "ON activity_categories;"
    )
    op.drop_index(
        "activity_categories_name_idx",
        table_name="activity_categories",
    )
    op.drop_index(
        "activity_categories_parent_idx",
        table_name="activity_categories",
    )
    op.drop_table("activity_categories")
