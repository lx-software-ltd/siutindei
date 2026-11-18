"""Optional upper bound on an activity price.

Revision ID: 0069_pricing_amount_max
Revises: 0068_listing_age_cap

``amount`` stays the price, and the lower bound when the fee is a
range. ``amount_max`` is null for a single price. A range stores a
higher upper bound. ``free`` has no upper bound.

The catalog version triggers snapshot the whole row, so the new
column reaches version history without a trigger change.

Seed assessment: no seed change. The column is nullable and both seed
prices omit it, so they stay single prices. No column is renamed or
dropped, no enum changes, and no table is added.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0069_pricing_amount_max"
down_revision: Union[str, None] = "0068_listing_age_cap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECK = (
    "(pricing_type = 'free' AND amount_max IS NULL) OR "
    "(pricing_type <> 'free' AND (amount_max IS NULL OR amount_max > amount))"
)


def upgrade() -> None:
    """Add the optional upper bound and its check."""
    op.add_column(
        "activity_pricing",
        sa.Column(
            "amount_max",
            sa.Numeric(10, 2),
            nullable=True,
            comment="Upper bound when the fee is a range. Null is one price.",
        ),
    )
    op.create_check_constraint(
        "pricing_amount_max_check",
        "activity_pricing",
        _CHECK,
    )


def downgrade() -> None:
    """Drop the upper bound. Ranged rows keep ``amount``."""
    op.drop_constraint(
        "pricing_amount_max_check",
        "activity_pricing",
        type_="check",
    )
    op.drop_column("activity_pricing", "amount_max")
