"""Rename owner_id to manager_id in organizations table.

This migration renames the owner_id column to manager_id to better reflect
the role terminology used throughout the application.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0009_rename_owner_to_manager"
down_revision: Union[str, None] = "0008_access_req_ticket_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename owner_id to manager_id in organizations table."""
    # Drop the old index
    op.drop_index("organizations_owner_id_idx", table_name="organizations")

    # Rename the column
    op.alter_column(
        "organizations",
        "owner_id",
        new_column_name="manager_id",
        comment="Cognito user sub (subject) identifier of the organization manager",
    )

    # Create new index with updated name
    op.create_index(
        "organizations_manager_id_idx",
        "organizations",
        ["manager_id"],
    )


def downgrade() -> None:
    """Rename manager_id back to owner_id in organizations table."""
    # Drop the new index
    op.drop_index("organizations_manager_id_idx", table_name="organizations")

    # Rename the column back
    op.alter_column(
        "organizations",
        "manager_id",
        new_column_name="owner_id",
        comment="Cognito user sub (subject) identifier of the organization owner",
    )

    # Recreate the old index
    op.create_index(
        "organizations_owner_id_idx",
        "organizations",
        ["owner_id"],
    )
