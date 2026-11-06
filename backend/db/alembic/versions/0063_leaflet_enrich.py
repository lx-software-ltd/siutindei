"""Leaflet source, stored leaflet files, and the vision model.

Revision ID: 0063_leaflet_enrich
Revises: 0062_location_status

Seed assessment: seed_data.sql has no org_enrichment rows.
``source`` is NOT NULL with server default ``website``, so existing
runs stay website runs. ``leaflet_items`` and ``leaflet_model`` are
nullable. The settings singleton inserted by 0055 needs no new value.
Existing seed SQL still runs. No new table or foreign key.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0063_leaflet_enrich"
down_revision: Union[str, None] = "0062_location_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RUNS = "org_enrichment_runs"
_SOURCE_CHECK = "org_enrichment_runs_source_check"


def upgrade() -> None:
    """Record leaflet runs and the optional vision model."""
    op.add_column(
        _RUNS,
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default="website",
        ),
    )
    op.create_check_constraint(
        _SOURCE_CHECK,
        _RUNS,
        "source IN ('website', 'leaflet')",
        postgresql_not_valid=True,
    )
    op.execute(f"ALTER TABLE {_RUNS} VALIDATE CONSTRAINT {_SOURCE_CHECK}")
    op.add_column(
        _RUNS,
        sa.Column("leaflet_items", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "org_enrichment_settings",
        sa.Column("leaflet_model", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Drop the leaflet columns."""
    op.drop_column("org_enrichment_settings", "leaflet_model")
    op.drop_column(_RUNS, "leaflet_items")
    op.drop_constraint(_SOURCE_CHECK, _RUNS, type_="check")
    op.drop_column(_RUNS, "source")
