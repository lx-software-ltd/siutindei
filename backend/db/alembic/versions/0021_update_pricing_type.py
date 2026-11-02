"""Update pricing type enum and add free trial flag."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_update_pricing_type"
down_revision: Union[str, None] = "0020_allow_wrap_minutes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Update pricing type enum and add free trial flag."""
    op.add_column(
        "activity_pricing",
        sa.Column(
            "free_trial_class_offered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.drop_constraint(
        "pricing_sessions_count_check",
        "activity_pricing",
        type_="check",
    )
    op.execute("DELETE FROM activity_pricing WHERE pricing_type = 'per_month'")
    op.execute(
        "CREATE TYPE pricing_type_new AS ENUM "
        "('per_class', 'per_sessions', 'per_hour', 'per_day')"
    )
    op.execute(
        "ALTER TABLE activity_pricing "
        "ALTER COLUMN pricing_type TYPE pricing_type_new "
        "USING pricing_type::text::pricing_type_new"
    )
    op.execute("DROP TYPE pricing_type")
    op.execute("ALTER TYPE pricing_type_new RENAME TO pricing_type")
    op.create_check_constraint(
        "pricing_sessions_count_check",
        "activity_pricing",
        "(pricing_type <> 'per_sessions') OR "
        "(sessions_count IS NOT NULL AND sessions_count > 0)",
    )


def downgrade() -> None:
    """Revert pricing type enum and remove free trial flag."""
    op.drop_constraint(
        "pricing_sessions_count_check",
        "activity_pricing",
        type_="check",
    )
    op.execute(
        "DELETE FROM activity_pricing " "WHERE pricing_type IN ('per_hour', 'per_day')"
    )
    op.execute(
        "CREATE TYPE pricing_type_old AS ENUM "
        "('per_class', 'per_month', 'per_sessions')"
    )
    op.execute(
        "ALTER TABLE activity_pricing "
        "ALTER COLUMN pricing_type TYPE pricing_type_old "
        "USING pricing_type::text::pricing_type_old"
    )
    op.execute("DROP TYPE pricing_type")
    op.execute("ALTER TYPE pricing_type_old RENAME TO pricing_type")
    op.create_check_constraint(
        "pricing_sessions_count_check",
        "activity_pricing",
        "(pricing_type <> 'per_sessions') OR "
        "(sessions_count IS NOT NULL AND sessions_count > 0)",
    )
    op.drop_column("activity_pricing", "free_trial_class_offered")
