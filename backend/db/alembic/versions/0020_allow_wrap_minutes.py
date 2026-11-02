"""Allow overnight schedule minutes (start != end)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0020_allow_wrap_minutes"
down_revision: Union[str, None] = "0019_add_i18n_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow start_minutes_utc after end_minutes_utc."""
    op.drop_constraint(
        "schedule_minutes_order",
        "activity_schedule",
        type_="check",
    )
    op.create_check_constraint(
        "schedule_minutes_order",
        "activity_schedule",
        "start_minutes_utc IS NULL OR end_minutes_utc IS NULL OR "
        "start_minutes_utc != end_minutes_utc",
    )


def downgrade() -> None:
    """Restore start_minutes_utc < end_minutes_utc constraint."""
    op.drop_constraint(
        "schedule_minutes_order",
        "activity_schedule",
        type_="check",
    )
    op.create_check_constraint(
        "schedule_minutes_order",
        "activity_schedule",
        "start_minutes_utc IS NULL OR end_minutes_utc IS NULL OR "
        "start_minutes_utc < end_minutes_utc",
    )
