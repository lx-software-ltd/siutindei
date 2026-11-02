"""Drop denormalized district and country from locations.

These columns were kept for backward compatibility but are now
fully replaced by the area_id FK to geographic_areas.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_drop_loc_dist_ctry"
down_revision: Union[str, None] = "0014_add_geo_areas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop district and country columns from locations."""
    op.drop_index("locations_district_idx", table_name="locations", if_exists=True)
    op.drop_column("locations", "district")
    op.drop_column("locations", "country")


def downgrade() -> None:
    """Re-add district and country columns to locations."""
    op.add_column(
        "locations",
        sa.Column(
            "country",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'Hong Kong'"),
        ),
    )
    op.add_column(
        "locations",
        sa.Column("district", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    # Backfill from geographic_areas
    op.execute("""
        UPDATE locations l
        SET district = ga.name
        FROM geographic_areas ga
        WHERE ga.id = l.area_id;
    """)
    op.execute("""
        UPDATE locations l
        SET country = root.name
        FROM geographic_areas ga
        JOIN geographic_areas root ON root.id IS NOT DISTINCT FROM (
            WITH RECURSIVE ancestors AS (
                SELECT id, parent_id, name FROM geographic_areas WHERE id = ga.id
                UNION ALL
                SELECT g.id, g.parent_id, g.name
                FROM geographic_areas g JOIN ancestors a ON g.id = a.parent_id
            )
            SELECT id FROM ancestors WHERE parent_id IS NULL LIMIT 1
        )
        WHERE ga.id = l.area_id;
    """)
    op.create_index("locations_district_idx", "locations", ["district"])
