"""Add Hong Kong neighbourhoods and point locations at them.

Seed assessment: seed_data.sql locations now look up neighbourhood
rows (Central, Wan Chai, Tsim Sha Tsui) instead of their districts.
No new columns. Existing seed inserts still run after this upgrade
because those neighbourhood names exist. Downgrade moves locations
back onto the parent district before deleting the rows.
"""

from __future__ import annotations

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert

revision: str = "0045_hk_neighbourhoods"
down_revision: Union[str, None] = "0044_location_enrichment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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

LOCATIONS = sa.table(
    "locations",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("area_id", postgresql.UUID(as_uuid=True)),
    sa.column("lat", sa.Float()),
    sa.column("lng", sa.Float()),
)


def _catalog():
    """Load after Alembic adds backend/src to sys.path."""
    from app.data.hk_neighbourhoods import NEIGHBOURHOODS
    from app.data.hk_neighbourhoods import nearest_in_district

    return NEIGHBOURHOODS, nearest_in_district


def _hk_district_ids(connection: sa.Connection) -> dict[str, object]:
    rows = connection.execute(
        sa.text(
            """
            SELECT d.name, d.id
            FROM geographic_areas d
            JOIN geographic_areas region ON d.parent_id = region.id
            JOIN geographic_areas country ON region.parent_id = country.id
            WHERE d.level = 'district'
              AND country.code = 'HK'
            """
        )
    ).all()
    return {name: area_id for name, area_id in rows}


def _insert_neighbourhoods(connection: sa.Connection) -> None:
    neighbourhoods, _nearest = _catalog()
    parents = _hk_district_ids(connection)
    missing = sorted({item.district for item in neighbourhoods} - set(parents))
    if missing:
        msg = f"Hong Kong districts missing: {', '.join(missing)}"
        raise RuntimeError(msg)
    for item in neighbourhoods:
        stmt = (
            pg_insert(GEO_AREAS)
            .values(
                id=item.id,
                parent_id=parents[item.district],
                name=item.name,
                name_translations={"en": item.name, "zh-HK": item.name_zh},
                level="neighbourhood",
                code=None,
                active=True,
                display_order=item.display_order,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        connection.execute(stmt)


def _backfill_locations(connection: sa.Connection) -> None:
    rows = connection.execute(
        sa.text(
            """
            SELECT l.id, l.lat, l.lng, d.name
            FROM locations l
            JOIN geographic_areas d ON d.id = l.area_id
            WHERE d.level = 'district'
              AND EXISTS (
                SELECT 1
                FROM geographic_areas child
                WHERE child.parent_id = d.id
                  AND child.level = 'neighbourhood'
              )
            """
        )
    ).all()
    _unused, nearest_in_district = _catalog()
    del _unused
    for location_id, lat, lng, district_name in rows:
        picked = nearest_in_district(
            district_name,
            None if lat is None else float(lat),
            None if lng is None else float(lng),
        )
        if picked is None:
            continue
        connection.execute(
            sa.update(LOCATIONS)
            .where(LOCATIONS.c.id == location_id)
            .values(area_id=picked.id)
        )


def upgrade() -> None:
    """Insert neighbourhoods and move Hong Kong locations onto them."""
    connection = op.get_bind()
    _insert_neighbourhoods(connection)
    _backfill_locations(connection)


def downgrade() -> None:
    """Point locations at the parent district and delete neighbourhoods."""
    connection = op.get_bind()
    neighbourhoods, _nearest = _catalog()
    ids = [item.id for item in neighbourhoods]
    parent_id = (
        sa.select(GEO_AREAS.c.parent_id)
        .where(GEO_AREAS.c.id == LOCATIONS.c.area_id)
        .scalar_subquery()
    )
    connection.execute(
        sa.update(LOCATIONS)
        .where(LOCATIONS.c.area_id.in_(ids))
        .values(area_id=parent_id)
    )
    connection.execute(sa.delete(GEO_AREAS).where(GEO_AREAS.c.id.in_(ids)))
