"""Dates on schedules, so a camp or workshop can list its sessions.

Revision ID: 0067_schedule_dates
Revises: 0066_family_guide_taxonomy

``starts_on`` and ``ends_on`` are Hong Kong calendar dates. A dated
schedule is one session: its weekly entries give the daily hours on
the weekdays it runs between the two dates. ``schedule_type`` stays
``weekly``, so no new enum value reaches an old client.

The unique key gains ``starts_on`` with ``NULLS NOT DISTINCT``: an
undated schedule stays one per activity, venue, and language set, and
a camp can hold one session per start date. PostgreSQL 15 or later is
required; Aurora runs 16.

The catalog version triggers snapshot the whole row, so the new
columns reach version history without a trigger change.

Seed assessment: no seed change. Both columns are nullable and the
check passes when both are null, which is every seed row. No column is
renamed or dropped, no enum changes, and no table is added.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0067_schedule_dates"
down_revision: Union[str, None] = "0066_family_guide_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_UNIQUE = "schedule_unique_activity_location_languages"
_NEW_UNIQUE = "schedule_unique_activity_location_languages_start"


def upgrade() -> None:
    """Add the dates, their check, and the wider unique key."""
    op.add_column(
        "activity_schedule",
        sa.Column(
            "starts_on",
            sa.Date(),
            nullable=True,
            comment="First day of a dated session, Hong Kong calendar",
        ),
    )
    op.add_column(
        "activity_schedule",
        sa.Column(
            "ends_on",
            sa.Date(),
            nullable=True,
            comment="Last day of a dated session, Hong Kong calendar",
        ),
    )
    op.create_check_constraint(
        "schedule_dates_check",
        "activity_schedule",
        "(starts_on IS NULL AND ends_on IS NULL) OR "
        "(starts_on IS NOT NULL AND ends_on IS NOT NULL AND ends_on >= starts_on)",
    )
    op.drop_constraint(_OLD_UNIQUE, "activity_schedule", type_="unique")
    op.execute(
        f"CREATE UNIQUE INDEX {_NEW_UNIQUE} ON activity_schedule "
        "(activity_id, location_id, languages, starts_on) NULLS NOT DISTINCT"
    )
    op.create_index(
        "activity_schedule_ends_on_idx",
        "activity_schedule",
        ["ends_on"],
        postgresql_where=sa.text("ends_on IS NOT NULL"),
    )


def downgrade() -> None:
    """Drop dated sessions after the first per key, then the columns."""
    op.execute(
        "DELETE FROM activity_schedule AS s USING activity_schedule AS keep "
        "WHERE s.activity_id = keep.activity_id "
        "AND s.location_id = keep.location_id "
        "AND s.languages = keep.languages "
        "AND s.starts_on IS NOT NULL "
        "AND (keep.starts_on IS NULL OR keep.starts_on < s.starts_on)"
    )
    op.drop_index("activity_schedule_ends_on_idx", table_name="activity_schedule")
    op.execute(f"DROP INDEX IF EXISTS {_NEW_UNIQUE}")
    op.create_unique_constraint(
        _OLD_UNIQUE,
        "activity_schedule",
        ["activity_id", "location_id", "languages"],
    )
    op.drop_constraint("schedule_dates_check", "activity_schedule", type_="check")
    op.drop_column("activity_schedule", "ends_on")
    op.drop_column("activity_schedule", "starts_on")
