"""Add translation JSONB fields for localized text."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_add_i18n_fields"
down_revision: Union[str, None] = "0018_add_activity_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add translation JSONB fields."""
    op.add_column(
        "organizations",
        sa.Column(
            "name_translations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Language map for non-English name translations",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "description_translations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Language map for non-English description translations",
        ),
    )

    op.add_column(
        "activities",
        sa.Column(
            "name_translations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Language map for non-English name translations",
        ),
    )
    op.add_column(
        "activities",
        sa.Column(
            "description_translations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Language map for non-English description translations",
        ),
    )

    op.add_column(
        "activity_categories",
        sa.Column(
            "name_translations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Language map for non-English name translations",
        ),
    )

    op.add_column(
        "geographic_areas",
        sa.Column(
            "name_translations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Language map for non-English name translations",
        ),
    )


def downgrade() -> None:
    """Remove translation JSONB fields."""
    op.drop_column("geographic_areas", "name_translations")
    op.drop_column("activity_categories", "name_translations")
    op.drop_column("activities", "description_translations")
    op.drop_column("activities", "name_translations")
    op.drop_column("organizations", "description_translations")
    op.drop_column("organizations", "name_translations")
