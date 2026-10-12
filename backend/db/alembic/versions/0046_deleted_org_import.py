"""Let a deleted organization block a later import.

Revision ID: 0046_deleted_org_import
Revises: 0045_hk_neighbourhoods

Seed assessment: organization_merges.survivor_org_id becomes nullable.
seed_data.sql does not insert organization_merges. No seed column,
enum, or foreign key used by existing seed rows changes. Existing
merge rows keep their survivor.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0046_deleted_org_import"
down_revision: Union[str, None] = "0045_hk_neighbourhoods"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """A null survivor means the organization was deleted."""
    op.alter_column(
        "organization_merges",
        "survivor_org_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    """Drop deletion rows, then require a survivor again."""
    op.execute("DELETE FROM organization_merges WHERE survivor_org_id IS NULL")
    op.alter_column(
        "organization_merges",
        "survivor_org_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
