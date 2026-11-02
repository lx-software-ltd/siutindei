"""Index the first weekly entry of each schedule.

Revision ID: 0058_entry_order_idx
Revises: 0057_dq_enrich_trigger

Seed assessment: index only. ``seed_data.sql`` is unchanged.
No new column, table, check, or seed row.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0058_entry_order_idx"
down_revision: Union[str, None] = "0057_dq_enrich_trigger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "activity_schedule_entries_order_idx"
_TABLE = "activity_schedule_entries"
_COLUMNS = ["schedule_id", "day_of_week_utc", "start_minutes_utc", "id"]


def upgrade() -> None:
    """Serve DISTINCT ON (schedule_id) ordered by day, start, and id."""
    op.create_index(_INDEX, _TABLE, _COLUMNS)


def downgrade() -> None:
    """Drop the schedule-entry ordering index."""
    op.drop_index(_INDEX, table_name=_TABLE)
