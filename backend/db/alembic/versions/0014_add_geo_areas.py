"""Add geographic_areas table and link locations.

Creates a hierarchical geographic_areas table for validated
country/region/city/district lookups.  Seeds Hong Kong (18 districts),
Singapore (27 planning areas), and UAE (7 emirates with key districts).
Adds area_id FK to locations and backfills from existing district+country.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_add_geo_areas"
down_revision: Union[str, None] = "0013_add_loc_country"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Seed data  (id, parent_id, name, level, code, active, display_order)
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid4())


def _build_seed_data() -> list[dict]:
    """Build the full geographic area seed data."""
    rows: list[dict] = []

    # ---- Hong Kong ----
    hk_id = _uuid()
    rows.append(
        {
            "id": hk_id,
            "parent_id": None,
            "name": "Hong Kong",
            "level": "country",
            "code": "HK",
            "active": True,
            "display_order": 1,
        }
    )
    hk_districts = [
        "Central and Western",
        "Eastern",
        "Southern",
        "Wan Chai",
        "Kowloon City",
        "Kwun Tong",
        "Sham Shui Po",
        "Wong Tai Sin",
        "Yau Tsim Mong",
        "Islands",
        "Kwai Tsing",
        "North",
        "Sai Kung",
        "Sha Tin",
        "Tai Po",
        "Tsuen Wan",
        "Tuen Mun",
        "Yuen Long",
    ]
    for i, d in enumerate(hk_districts, 1):
        rows.append(
            {
                "id": _uuid(),
                "parent_id": hk_id,
                "name": d,
                "level": "district",
                "code": None,
                "active": True,
                "display_order": i,
            }
        )

    # ---- Singapore ----
    sg_id = _uuid()
    rows.append(
        {
            "id": sg_id,
            "parent_id": None,
            "name": "Singapore",
            "level": "country",
            "code": "SG",
            "active": False,
            "display_order": 2,
        }
    )
    sg_districts = [
        "Ang Mo Kio",
        "Bedok",
        "Bishan",
        "Bukit Batok",
        "Bukit Merah",
        "Bukit Panjang",
        "Bukit Timah",
        "Central Area",
        "Choa Chu Kang",
        "Clementi",
        "Geylang",
        "Hougang",
        "Jurong East",
        "Jurong West",
        "Kallang",
        "Marine Parade",
        "Novena",
        "Pasir Ris",
        "Punggol",
        "Queenstown",
        "Sembawang",
        "Sengkang",
        "Serangoon",
        "Tampines",
        "Toa Payoh",
        "Woodlands",
        "Yishun",
    ]
    for i, d in enumerate(sg_districts, 1):
        rows.append(
            {
                "id": _uuid(),
                "parent_id": sg_id,
                "name": d,
                "level": "district",
                "code": None,
                "active": True,
                "display_order": i,
            }
        )

    # ---- UAE ----
    ae_id = _uuid()
    rows.append(
        {
            "id": ae_id,
            "parent_id": None,
            "name": "United Arab Emirates",
            "level": "country",
            "code": "AE",
            "active": False,
            "display_order": 3,
        }
    )

    uae_structure: dict[str, list[str]] = {
        "Abu Dhabi": ["Abu Dhabi Island", "Al Ain", "Al Dhafra"],
        "Dubai": [
            "Bur Dubai",
            "Deira",
            "Downtown Dubai",
            "Dubai Marina",
            "Jumeirah",
            "Business Bay",
            "Al Barsha",
        ],
        "Sharjah": ["Sharjah City", "Al Dhaid"],
        "Ajman": ["Ajman City"],
        "Ras Al Khaimah": ["RAK City"],
        "Fujairah": ["Fujairah City"],
        "Umm Al Quwain": ["UAQ City"],
    }
    for eidx, (emirate, districts) in enumerate(uae_structure.items(), 1):
        emirate_id = _uuid()
        rows.append(
            {
                "id": emirate_id,
                "parent_id": ae_id,
                "name": emirate,
                "level": "region",
                "code": None,
                "active": True,
                "display_order": eidx,
            }
        )
        for didx, d in enumerate(districts, 1):
            rows.append(
                {
                    "id": _uuid(),
                    "parent_id": emirate_id,
                    "name": d,
                    "level": "district",
                    "code": None,
                    "active": True,
                    "display_order": didx,
                }
            )

    return rows


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """Create geographic_areas and link to locations."""

    # 1. Create geographic_areas table
    op.create_table(
        "geographic_areas",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("geographic_areas.id", ondelete="CASCADE"),
            nullable=True,
            comment="NULL for root (country) nodes",
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "level",
            sa.Text(),
            nullable=False,
            comment="country | region | city | district",
        ),
        sa.Column(
            "code",
            sa.Text(),
            nullable=True,
            comment="ISO 3166-1 alpha-2 for countries (HK, SG, AE)",
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Only active countries (and their children) are shown",
        ),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint("parent_id", "name", name="uq_geo_area_parent_name"),
    )

    op.create_index("geo_areas_parent_idx", "geographic_areas", ["parent_id"])
    op.create_index("geo_areas_level_idx", "geographic_areas", ["level"])
    op.create_index("geo_areas_code_idx", "geographic_areas", ["code"])

    # Grant permissions
    op.execute("GRANT SELECT ON geographic_areas TO siutindei_app;")
    op.execute("GRANT SELECT, INSERT, UPDATE ON geographic_areas TO siutindei_admin;")

    # 2. Seed data
    seed = _build_seed_data()
    geo_table = sa.table(
        "geographic_areas",
        sa.column("id", postgresql.UUID),
        sa.column("parent_id", postgresql.UUID),
        sa.column("name", sa.Text),
        sa.column("level", sa.Text),
        sa.column("code", sa.Text),
        sa.column("active", sa.Boolean),
        sa.column("display_order", sa.Integer),
    )
    op.bulk_insert(geo_table, seed)

    # 3. Add area_id column to locations (nullable initially for backfill)
    op.add_column(
        "locations",
        sa.Column(
            "area_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="FK to geographic_areas leaf node",
        ),
    )

    # 4. Backfill area_id from country + district
    op.execute("""
        UPDATE locations l
        SET area_id = ga.id
        FROM geographic_areas ga
        JOIN geographic_areas parent ON ga.parent_id = parent.id
        WHERE parent.level = 'country'
          AND parent.name = l.country
          AND ga.name = l.district
          AND ga.level = 'district';
    """)

    # 5. For any remaining unmatched rows, try matching district name only
    # (handles edge cases where country name differs slightly)
    op.execute("""
        UPDATE locations l
        SET area_id = ga.id
        FROM geographic_areas ga
        WHERE l.area_id IS NULL
          AND ga.name = l.district
          AND ga.level = 'district';
    """)

    # 6. Make area_id NOT NULL and add FK constraint
    # First handle any rows that still have NULL area_id by assigning
    # the first matching HK district or leaving them for manual fix.
    op.execute("""
        UPDATE locations l
        SET area_id = (
            SELECT ga.id
            FROM geographic_areas ga
            JOIN geographic_areas parent ON ga.parent_id = parent.id
            WHERE parent.code = 'HK'
              AND ga.level = 'district'
            ORDER BY ga.display_order
            LIMIT 1
        )
        WHERE l.area_id IS NULL;
    """)

    op.alter_column("locations", "area_id", nullable=False)
    op.create_foreign_key(
        "fk_locations_area_id",
        "locations",
        "geographic_areas",
        ["area_id"],
        ["id"],
    )
    op.create_index("locations_area_idx", "locations", ["area_id"])


def downgrade() -> None:
    """Remove geographic_areas and area_id from locations."""

    op.drop_index("locations_area_idx", table_name="locations")
    op.drop_constraint("fk_locations_area_id", "locations", type_="foreignkey")
    op.drop_column("locations", "area_id")

    op.drop_index("geo_areas_code_idx", table_name="geographic_areas")
    op.drop_index("geo_areas_level_idx", table_name="geographic_areas")
    op.drop_index("geo_areas_parent_idx", table_name="geographic_areas")
    op.drop_table("geographic_areas")
