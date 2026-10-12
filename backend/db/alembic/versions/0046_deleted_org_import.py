"""Let an admin delete block a later import.

Revision ID: 0046_deleted_org_import
Revises: 0045_hk_neighbourhoods

Seed assessment: organization_merges.kind is NOT NULL with server
default ``merge``, and survivor_org_id becomes nullable. The check
allows a null survivor only when kind is ``delete``. seed_data.sql
does not insert organization_merges. Existing merge rows keep their
survivor and receive kind ``merge``. No seed column is renamed or
dropped, and no enum used by seed rows changes.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0046_deleted_org_import"
down_revision: Union[str, None] = "0045_hk_neighbourhoods"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KIND_SURVIVOR = (
    "(kind = 'merge' AND survivor_org_id IS NOT NULL) "
    "OR (kind = 'delete' AND survivor_org_id IS NULL)"
)


def upgrade() -> None:
    """Remember a deleted organization without a survivor."""
    op.add_column(
        "organization_merges",
        sa.Column(
            "kind",
            sa.Text(),
            nullable=False,
            server_default="merge",
        ),
    )
    op.alter_column(
        "organization_merges",
        "survivor_org_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_check_constraint(
        "organization_merges_kind_survivor_check",
        "organization_merges",
        _KIND_SURVIVOR,
    )


def downgrade() -> None:
    """Require a survivor again after every deletion has been exported.

    Raising leaves the rows in place. Deleting them here would let a
    later upgrade import those organizations again.
    """
    count = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM organization_merges "
                "WHERE kind = 'delete' OR survivor_org_id IS NULL"
            )
        )
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            f"{count} deleted-organization rows would be lost. "
            "Forget them from Data quality, or export and delete "
            "organization_merges rows where kind = 'delete', then downgrade."
        )
    op.drop_constraint(
        "organization_merges_kind_survivor_check",
        "organization_merges",
        type_="check",
    )
    op.alter_column(
        "organization_merges",
        "survivor_org_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_column("organization_merges", "kind")
