"""Move schedules to weekly entry groups."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_weekly_sched_entries"
down_revision: Union[str, None] = "0024_rename_search_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create schedule entries and keep weekly schedules only."""
    op.create_table(
        "activity_schedule_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activity_schedule.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day_of_week_utc", sa.SmallInteger(), nullable=False),
        sa.Column("start_minutes_utc", sa.Integer(), nullable=False),
        sa.Column("end_minutes_utc", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "day_of_week_utc BETWEEN 0 AND 6",
            name="schedule_entry_day_range",
        ),
        sa.CheckConstraint(
            "start_minutes_utc BETWEEN 0 AND 1439",
            name="schedule_entry_start_minutes_range",
        ),
        sa.CheckConstraint(
            "end_minutes_utc BETWEEN 0 AND 1439",
            name="schedule_entry_end_minutes_range",
        ),
        sa.CheckConstraint(
            "start_minutes_utc != end_minutes_utc",
            name="schedule_entry_minutes_order",
        ),
        sa.UniqueConstraint(
            "schedule_id",
            "day_of_week_utc",
            "start_minutes_utc",
            "end_minutes_utc",
            name="schedule_entry_unique",
        ),
    )
    op.create_index(
        "activity_schedule_entries_schedule_idx",
        "activity_schedule_entries",
        ["schedule_id"],
    )
    op.create_index(
        "activity_schedule_entries_day_idx",
        "activity_schedule_entries",
        [
            "day_of_week_utc",
            "start_minutes_utc",
            "end_minutes_utc",
        ],
    )

    op.execute(
        """
        INSERT INTO activity_schedule_entries (
          id,
          schedule_id,
          day_of_week_utc,
          start_minutes_utc,
          end_minutes_utc
        )
        SELECT
          gen_random_uuid(),
          id,
          day_of_week_utc,
          start_minutes_utc,
          end_minutes_utc
        FROM activity_schedule
        WHERE schedule_type = 'weekly'
          AND day_of_week_utc IS NOT NULL
          AND start_minutes_utc IS NOT NULL
          AND end_minutes_utc IS NOT NULL
        """
    )

    op.execute("DELETE FROM activity_schedule WHERE schedule_type <> 'weekly'")

    op.drop_index(
        "activity_schedule_type_weekly_idx",
        table_name="activity_schedule",
    )
    op.drop_index(
        "activity_schedule_type_monthly_idx",
        table_name="activity_schedule",
    )
    op.drop_index(
        "activity_schedule_date_idx",
        table_name="activity_schedule",
    )
    op.drop_constraint(
        "schedule_day_of_week_range",
        "activity_schedule",
        type_="check",
    )
    op.drop_constraint(
        "schedule_day_of_month_range",
        "activity_schedule",
        type_="check",
    )
    op.drop_constraint(
        "schedule_start_minutes_range",
        "activity_schedule",
        type_="check",
    )
    op.drop_constraint(
        "schedule_end_minutes_range",
        "activity_schedule",
        type_="check",
    )
    op.drop_constraint(
        "schedule_minutes_order",
        "activity_schedule",
        type_="check",
    )
    op.drop_constraint(
        "schedule_date_order",
        "activity_schedule",
        type_="check",
    )
    op.drop_constraint(
        "schedule_type_fields_check",
        "activity_schedule",
        type_="check",
    )

    op.drop_column("activity_schedule", "day_of_week_utc")
    op.drop_column("activity_schedule", "day_of_month")
    op.drop_column("activity_schedule", "start_minutes_utc")
    op.drop_column("activity_schedule", "end_minutes_utc")
    op.drop_column("activity_schedule", "start_at_utc")
    op.drop_column("activity_schedule", "end_at_utc")

    op.create_unique_constraint(
        "schedule_unique_activity_location_languages",
        "activity_schedule",
        [
            "activity_id",
            "location_id",
            "languages",
        ],
    )

    op.execute("ALTER TYPE schedule_type RENAME TO schedule_type_old")
    op.execute("CREATE TYPE schedule_type AS ENUM ('weekly')")
    op.execute(
        "ALTER TABLE activity_schedule "
        "ALTER COLUMN schedule_type TYPE schedule_type "
        "USING schedule_type::text::schedule_type"
    )
    op.execute("DROP TYPE schedule_type_old")
    op.create_check_constraint(
        "schedule_type_weekly_only",
        "activity_schedule",
        "schedule_type = 'weekly'",
    )


def downgrade() -> None:
    """Restore weekly/monthly/date-specific schedules."""
    op.drop_constraint(
        "schedule_type_weekly_only",
        "activity_schedule",
        type_="check",
    )
    op.drop_constraint(
        "schedule_unique_activity_location_languages",
        "activity_schedule",
        type_="unique",
    )

    op.execute("ALTER TYPE schedule_type RENAME TO schedule_type_new")
    op.execute(
        "CREATE TYPE schedule_type AS ENUM ('weekly', 'monthly', 'date_specific')"
    )
    op.execute(
        "ALTER TABLE activity_schedule "
        "ALTER COLUMN schedule_type TYPE schedule_type "
        "USING schedule_type::text::schedule_type"
    )
    op.execute("DROP TYPE schedule_type_new")

    op.add_column(
        "activity_schedule",
        sa.Column(
            "end_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "activity_schedule",
        sa.Column(
            "start_at_utc",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "activity_schedule",
        sa.Column("end_minutes_utc", sa.Integer(), nullable=True),
    )
    op.add_column(
        "activity_schedule",
        sa.Column("start_minutes_utc", sa.Integer(), nullable=True),
    )
    op.add_column(
        "activity_schedule",
        sa.Column("day_of_month", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "activity_schedule",
        sa.Column("day_of_week_utc", sa.SmallInteger(), nullable=True),
    )

    op.execute(
        """
        UPDATE activity_schedule AS s
        SET day_of_week_utc = e.day_of_week_utc,
            start_minutes_utc = e.start_minutes_utc,
            end_minutes_utc = e.end_minutes_utc
        FROM (
          SELECT DISTINCT ON (schedule_id)
            schedule_id,
            day_of_week_utc,
            start_minutes_utc,
            end_minutes_utc
          FROM activity_schedule_entries
          ORDER BY schedule_id, day_of_week_utc, start_minutes_utc, id
        ) AS e
        WHERE s.id = e.schedule_id
        """
    )

    op.create_check_constraint(
        "schedule_day_of_week_range",
        "activity_schedule",
        "day_of_week_utc BETWEEN 0 AND 6",
    )
    op.create_check_constraint(
        "schedule_day_of_month_range",
        "activity_schedule",
        "day_of_month BETWEEN 1 AND 31",
    )
    op.create_check_constraint(
        "schedule_start_minutes_range",
        "activity_schedule",
        "start_minutes_utc BETWEEN 0 AND 1439",
    )
    op.create_check_constraint(
        "schedule_end_minutes_range",
        "activity_schedule",
        "end_minutes_utc BETWEEN 0 AND 1439",
    )
    op.create_check_constraint(
        "schedule_minutes_order",
        "activity_schedule",
        "start_minutes_utc IS NULL OR end_minutes_utc IS NULL OR "
        "start_minutes_utc != end_minutes_utc",
    )
    op.create_check_constraint(
        "schedule_date_order",
        "activity_schedule",
        "start_at_utc IS NULL OR end_at_utc IS NULL OR start_at_utc < end_at_utc",
    )
    op.create_check_constraint(
        "schedule_type_fields_check",
        "activity_schedule",
        "("
        "schedule_type = 'weekly' AND "
        "day_of_week_utc IS NOT NULL AND "
        "start_minutes_utc IS NOT NULL AND "
        "end_minutes_utc IS NOT NULL AND "
        "day_of_month IS NULL AND "
        "start_at_utc IS NULL AND "
        "end_at_utc IS NULL"
        ") OR ("
        "schedule_type = 'monthly' AND "
        "day_of_month IS NOT NULL AND "
        "start_minutes_utc IS NOT NULL AND "
        "end_minutes_utc IS NOT NULL AND "
        "day_of_week_utc IS NULL AND "
        "start_at_utc IS NULL AND "
        "end_at_utc IS NULL"
        ") OR ("
        "schedule_type = 'date_specific' AND "
        "start_at_utc IS NOT NULL AND "
        "end_at_utc IS NOT NULL AND "
        "day_of_week_utc IS NULL AND "
        "day_of_month IS NULL AND "
        "start_minutes_utc IS NULL AND "
        "end_minutes_utc IS NULL"
        ")",
    )

    op.create_index(
        "activity_schedule_type_weekly_idx",
        "activity_schedule",
        [
            "schedule_type",
            "day_of_week_utc",
            "start_minutes_utc",
            "end_minutes_utc",
        ],
    )
    op.create_index(
        "activity_schedule_type_monthly_idx",
        "activity_schedule",
        [
            "schedule_type",
            "day_of_month",
            "start_minutes_utc",
            "end_minutes_utc",
        ],
    )
    op.create_index(
        "activity_schedule_date_idx",
        "activity_schedule",
        ["start_at_utc", "end_at_utc"],
    )

    op.drop_index(
        "activity_schedule_entries_day_idx",
        table_name="activity_schedule_entries",
    )
    op.drop_index(
        "activity_schedule_entries_schedule_idx",
        table_name="activity_schedule_entries",
    )
    op.drop_table("activity_schedule_entries")
