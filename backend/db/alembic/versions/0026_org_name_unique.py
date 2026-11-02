"""Add case-insensitive unique names for orgs, locations, activities."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_org_name_unique"
down_revision: Union[str, None] = "0025_weekly_sched_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add case-insensitive unique indexes for names."""
    _dedupe_organizations()
    _dedupe_locations()
    _dedupe_activities()

    op.create_index(
        "organizations_name_unique_ci",
        "organizations",
        [sa.text("lower(trim(name))")],
        unique=True,
    )
    op.create_index(
        "locations_org_address_unique_ci",
        "locations",
        ["org_id", sa.text("lower(trim(address))")],
        unique=True,
    )
    op.create_index(
        "activities_org_name_unique_ci",
        "activities",
        ["org_id", sa.text("lower(trim(name))")],
        unique=True,
    )


def downgrade() -> None:
    """Drop case-insensitive unique indexes for names."""
    op.drop_index(
        "activities_org_name_unique_ci",
        table_name="activities",
    )
    op.drop_index(
        "locations_org_address_unique_ci",
        table_name="locations",
    )
    op.drop_index(
        "organizations_name_unique_ci",
        table_name="organizations",
    )


def _dedupe_organizations() -> None:
    op.execute(
        """
        WITH ranked AS (
          SELECT
            id,
            trim(name) AS base_name,
            row_number() OVER (
              PARTITION BY lower(trim(name))
              ORDER BY id
            ) AS rn
          FROM organizations
          WHERE name IS NOT NULL
        ),
        updates AS (
          SELECT
            id,
            base_name,
            rn,
            ' (dup ' || rn::text || ')' AS suffix
          FROM ranked
          WHERE rn > 1
        )
        UPDATE organizations AS o
        SET name = substring(
          updates.base_name for GREATEST(1, 200 - length(updates.suffix))
        ) || updates.suffix
        FROM updates
        WHERE o.id = updates.id
        """
    )


def _dedupe_locations() -> None:
    op.execute(
        """
        WITH ranked AS (
          SELECT
            id,
            org_id,
            trim(address) AS base_address,
            row_number() OVER (
              PARTITION BY org_id, lower(trim(address))
              ORDER BY id
            ) AS rn
          FROM locations
          WHERE address IS NOT NULL
        ),
        updates AS (
          SELECT
            id,
            base_address,
            rn,
            ' (dup ' || rn::text || ')' AS suffix
          FROM ranked
          WHERE rn > 1
        )
        UPDATE locations AS l
        SET address = substring(
          updates.base_address for GREATEST(1, 500 - length(updates.suffix))
        ) || updates.suffix
        FROM updates
        WHERE l.id = updates.id
        """
    )


def _dedupe_activities() -> None:
    op.execute(
        """
        WITH ranked AS (
          SELECT
            id,
            org_id,
            trim(name) AS base_name,
            row_number() OVER (
              PARTITION BY org_id, lower(trim(name))
              ORDER BY id
            ) AS rn
          FROM activities
          WHERE name IS NOT NULL
        ),
        updates AS (
          SELECT
            id,
            base_name,
            rn,
            ' (dup ' || rn::text || ')' AS suffix
          FROM ranked
          WHERE rn > 1
        )
        UPDATE activities AS a
        SET name = substring(
          updates.base_name for GREATEST(1, 200 - length(updates.suffix))
        ) || updates.suffix
        FROM updates
        WHERE a.id = updates.id
        """
    )
