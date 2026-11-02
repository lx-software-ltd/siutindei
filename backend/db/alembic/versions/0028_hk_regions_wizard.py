"""Add HK macro regions and wizard activity categories.

Inserts Hong Kong Island, Kowloon, New Territories, and Islands as
level=region nodes under Hong Kong, reparents districts beneath them,
and seeds workshop/class/outdoor/indoor categories for the home wizard.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert

revision: str = "0028_hk_regions_wizard"
down_revision: Union[str, None] = "0027_add_feedback_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HK_ISLAND_ID = uuid.UUID("a1111111-1111-1111-1111-111111111101")
KOWLOON_ID = uuid.UUID("a1111111-1111-1111-1111-111111111102")
NEW_TERRITORIES_ID = uuid.UUID("a1111111-1111-1111-1111-111111111103")
ISLANDS_ID = uuid.UUID("a1111111-1111-1111-1111-111111111104")

WORKSHOP_CATEGORY_ID = uuid.UUID("c1111111-1111-1111-1111-111111111101")
CLASS_CATEGORY_ID = uuid.UUID("c1111111-1111-1111-1111-111111111102")
OUTDOOR_CATEGORY_ID = uuid.UUID("c1111111-1111-1111-1111-111111111103")
INDOOR_CATEGORY_ID = uuid.UUID("c1111111-1111-1111-1111-111111111104")

SPORT_CATEGORY_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")

PAINTING_ACTIVITY_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
DANCE_ACTIVITY_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

HK_ISLAND_DISTRICTS = (
    "Central and Western",
    "Eastern",
    "Southern",
    "Wan Chai",
)
KOWLOON_DISTRICTS = (
    "Kowloon City",
    "Kwun Tong",
    "Sham Shui Po",
    "Wong Tai Sin",
    "Yau Tsim Mong",
)
NEW_TERRITORIES_DISTRICTS = (
    "Kwai Tsing",
    "North",
    "Sai Kung",
    "Sha Tin",
    "Tai Po",
    "Tsuen Wan",
    "Tuen Mun",
    "Yuen Long",
)
ISLANDS_DISTRICTS = ("Islands",)

# District "Islands" already exists under HK; region row uses a temporary
# distinct name until districts are reparented, then renames to "Islands".
ISLANDS_REGION_STAGING_NAME = "Outlying Islands"

GEO_AREAS = sa.table(
    "geographic_areas",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("parent_id", postgresql.UUID(as_uuid=True)),
    sa.column("name", sa.Text()),
    sa.column("name_translations", postgresql.JSONB()),
    sa.column("level", sa.Text()),
    sa.column("code", sa.Text()),
    sa.column("active", sa.Boolean()),
    sa.column("display_order", sa.Integer()),
)

ACTIVITY_CATEGORIES = sa.table(
    "activity_categories",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("parent_id", postgresql.UUID(as_uuid=True)),
    sa.column("name", sa.Text()),
    sa.column("name_translations", postgresql.JSONB()),
    sa.column("display_order", sa.Integer()),
)

ACTIVITIES = sa.table(
    "activities",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("category_id", postgresql.UUID(as_uuid=True)),
)


def _hk_country_id(connection: sa.Connection) -> uuid.UUID:
    """Return the Hong Kong country geographic_areas row id."""

    row = connection.execute(
        sa.select(GEO_AREAS.c.id).where(
            sa.and_(GEO_AREAS.c.code == "HK", GEO_AREAS.c.level == "country")
        )
    ).first()
    if row is None:
        msg = "Hong Kong country row not found in geographic_areas"
        raise RuntimeError(msg)
    return row[0]


def _region_exists(connection: sa.Connection, region_id: uuid.UUID) -> bool:
    row = connection.execute(
        sa.select(sa.literal(1)).where(GEO_AREAS.c.id == region_id)
    ).first()
    return row is not None


def _insert_region(
    connection: sa.Connection,
    hk_country_id: uuid.UUID,
    region_id: uuid.UUID,
    name: str,
    code: str,
    name_en: str,
    name_zh: str,
    display_order: int,
) -> None:
    if _region_exists(connection, region_id):
        return
    connection.execute(
        sa.insert(GEO_AREAS).values(
            id=region_id,
            parent_id=hk_country_id,
            name=name,
            name_translations={"en": name_en, "zh-HK": name_zh},
            level="region",
            code=code,
            active=True,
            display_order=display_order,
        )
    )


def _reparent_districts(
    connection: sa.Connection,
    hk_country_id: uuid.UUID,
    region_id: uuid.UUID,
    district_names: tuple[str, ...],
) -> None:
    connection.execute(
        sa.update(GEO_AREAS)
        .where(
            sa.and_(
                GEO_AREAS.c.level == "district",
                GEO_AREAS.c.name.in_(district_names),
                GEO_AREAS.c.parent_id == hk_country_id,
            )
        )
        .values(parent_id=region_id)
    )


def _insert_category(
    connection: sa.Connection,
    category_id: uuid.UUID,
    name: str,
    name_translations: dict[str, str],
    display_order: int,
) -> None:
    stmt = (
        pg_insert(ACTIVITY_CATEGORIES)
        .values(
            id=category_id,
            parent_id=None,
            name=name,
            name_translations=name_translations,
            display_order=display_order,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    connection.execute(stmt)


def upgrade() -> None:
    """Insert HK regions, reparent districts, and seed wizard categories."""
    connection = op.get_bind()
    hk_country_id = _hk_country_id(connection)

    _insert_region(
        connection,
        hk_country_id,
        HK_ISLAND_ID,
        "Hong Kong Island",
        "hk_island",
        "Hong Kong Island",
        "香港島",
        1,
    )
    _insert_region(
        connection,
        hk_country_id,
        KOWLOON_ID,
        "Kowloon",
        "hk_kowloon",
        "Kowloon",
        "九龍",
        2,
    )
    _insert_region(
        connection,
        hk_country_id,
        NEW_TERRITORIES_ID,
        "New Territories",
        "hk_new_territories",
        "New Territories",
        "新界",
        3,
    )
    _insert_region(
        connection,
        hk_country_id,
        ISLANDS_ID,
        ISLANDS_REGION_STAGING_NAME,
        "hk_islands",
        "Islands",
        "離島",
        4,
    )

    _reparent_districts(connection, hk_country_id, HK_ISLAND_ID, HK_ISLAND_DISTRICTS)
    _reparent_districts(connection, hk_country_id, KOWLOON_ID, KOWLOON_DISTRICTS)
    _reparent_districts(
        connection,
        hk_country_id,
        NEW_TERRITORIES_ID,
        NEW_TERRITORIES_DISTRICTS,
    )
    _reparent_districts(connection, hk_country_id, ISLANDS_ID, ISLANDS_DISTRICTS)
    connection.execute(
        sa.update(GEO_AREAS).where(GEO_AREAS.c.id == ISLANDS_ID).values(name="Islands")
    )

    _insert_category(
        connection,
        WORKSHOP_CATEGORY_ID,
        "Workshop",
        {"en": "Workshop", "zh-HK": "工作坊"},
        2,
    )
    _insert_category(
        connection,
        CLASS_CATEGORY_ID,
        "Class",
        {"en": "Class", "zh-HK": "課程"},
        3,
    )
    _insert_category(
        connection,
        OUTDOOR_CATEGORY_ID,
        "Outdoor activity",
        {"en": "Outdoor activity", "zh-HK": "戶外活動"},
        4,
    )
    _insert_category(
        connection,
        INDOOR_CATEGORY_ID,
        "Indoor fun",
        {"en": "Indoor fun", "zh-HK": "室內玩樂"},
        5,
    )

    connection.execute(
        sa.update(ACTIVITIES)
        .where(ACTIVITIES.c.id == PAINTING_ACTIVITY_ID)
        .values(category_id=WORKSHOP_CATEGORY_ID)
    )
    connection.execute(
        sa.update(ACTIVITIES)
        .where(ACTIVITIES.c.id == DANCE_ACTIVITY_ID)
        .values(category_id=CLASS_CATEGORY_ID)
    )


def downgrade() -> None:
    """Restore flat HK districts and remove wizard categories."""
    connection = op.get_bind()
    hk_country_id = _hk_country_id(connection)
    region_ids = (HK_ISLAND_ID, KOWLOON_ID, NEW_TERRITORIES_ID, ISLANDS_ID)
    wizard_category_ids = (
        WORKSHOP_CATEGORY_ID,
        CLASS_CATEGORY_ID,
        OUTDOOR_CATEGORY_ID,
        INDOOR_CATEGORY_ID,
    )

    connection.execute(
        sa.update(ACTIVITIES)
        .where(ACTIVITIES.c.id.in_([PAINTING_ACTIVITY_ID, DANCE_ACTIVITY_ID]))
        .values(category_id=SPORT_CATEGORY_ID)
    )
    connection.execute(
        sa.delete(ACTIVITY_CATEGORIES).where(
            ACTIVITY_CATEGORIES.c.id.in_(wizard_category_ids)
        )
    )
    connection.execute(
        sa.update(GEO_AREAS)
        .where(
            sa.and_(
                GEO_AREAS.c.level == "district",
                GEO_AREAS.c.parent_id.in_(region_ids),
            )
        )
        .values(parent_id=hk_country_id)
    )
    connection.execute(
        sa.update(GEO_AREAS)
        .where(GEO_AREAS.c.id == ISLANDS_ID)
        .values(name=ISLANDS_REGION_STAGING_NAME)
    )
    connection.execute(sa.delete(GEO_AREAS).where(GEO_AREAS.c.id.in_(region_ids)))
