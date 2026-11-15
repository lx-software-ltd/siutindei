"""Stored listing ages stay between 0 and 18.

Revision ID: 0068_listing_age_cap
Revises: 0067_schedule_dates

Postgres stores an inclusive age as an exclusive upper bound, so 18 is
``upper(age_range) = 19``. The check matches ``MAX_LISTING_AGE`` in
``app.db.age_bounds``. Writes cap a higher age before insert; this
rejects a row that bypasses those writes.

Seed assessment: no seed change. Both seed activities are
``int4range(4, 9, '[]')`` and ``int4range(3, 7, '[]')``, which already
pass. No column is renamed or dropped, no enum changes, and no table
is added.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0068_listing_age_cap"
down_revision: Union[str, None] = "0067_schedule_dates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECK = "lower(age_range) >= 0 AND lower(age_range) <= 18 AND upper(age_range) <= 19"


def upgrade() -> None:
    """Reject a stored age outside 0 to 18."""
    op.create_check_constraint(
        "activities_age_range_check",
        "activities",
        _CHECK,
    )


def downgrade() -> None:
    """Remove the age check."""
    op.drop_constraint(
        "activities_age_range_check",
        "activities",
        type_="check",
    )
