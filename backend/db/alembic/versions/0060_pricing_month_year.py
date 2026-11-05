"""Add monthly and yearly pricing types.

Revision ID: 0060_pricing_month_year
Revises: 0059_import_merge

Seed assessment: no seed change. Existing seed prices stay
``per_class``. No new table, column, NOT NULL, or foreign key.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0060_pricing_month_year"
down_revision: Union[str, None] = "0059_import_merge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = (
    "'per_class', 'per_sessions', 'per_hour', 'per_day', 'free', "
    "'per_month', 'per_year'"
)
_OLD = "'per_class', 'per_sessions', 'per_hour', 'per_day', 'free'"
_CHECK = (
    "(pricing_type <> 'per_sessions') OR "
    "(sessions_count IS NOT NULL AND sessions_count > 0)"
)


def upgrade() -> None:
    """Add per_month and per_year to pricing_type."""
    _replace_enum(_NEW)


def downgrade() -> None:
    """Remove per_month and per_year."""
    op.execute(
        "DELETE FROM activity_pricing WHERE pricing_type IN ('per_month', 'per_year')"
    )
    _replace_enum(_OLD)


def _replace_enum(values: str) -> None:
    op.drop_constraint(
        "pricing_sessions_count_check",
        "activity_pricing",
        type_="check",
    )
    op.execute(f"CREATE TYPE pricing_type_new AS ENUM ({values})")
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
        _CHECK,
    )
