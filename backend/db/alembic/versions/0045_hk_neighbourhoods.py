"""Add Hong Kong neighbourhoods and point locations at them.

Seed assessment: seed_data.sql locations now look up neighbourhood
rows (Central, Wan Chai, Tsim Sha Tsui) instead of their districts.
New lat/lng columns are nullable, so existing seed inserts still run.
Downgrade moves locations back onto the parent district, drops the
review rows this upgrade added, and deletes the neighbourhood rows.
"""

from __future__ import annotations

import json
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

_ASSIGNMENT = "nearest_neighbourhood"

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


def _catalog():
    """Load after Alembic adds backend/src to sys.path."""
    from app.data.hk_neighbourhoods import DISTRICT_NAME_ZH
    from app.data.hk_neighbourhoods import HK_COUNTRY_NAME_ZH
    from app.data.hk_neighbourhoods import NEIGHBOURHOODS
    from app.data.hk_neighbourhoods import assign_among
    from app.data.hk_neighbourhoods import assign_in_district

    return (
        NEIGHBOURHOODS,
        assign_in_district,
        assign_among,
        DISTRICT_NAME_ZH,
        HK_COUNTRY_NAME_ZH,
    )


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
    neighbourhoods, *_rest = _catalog()
    parents = _hk_district_ids(connection)
    missing = sorted({item.district for item in neighbourhoods} - set(parents))
    if missing:
        msg = f"Hong Kong districts missing: {', '.join(missing)}"
        raise RuntimeError(msg)
    for item in neighbourhoods:
        parent_id = parents[item.district]
        old_id = _rename_name_collision(connection, parent_id, item.name, item.id)
        stmt = (
            pg_insert(GEO_AREAS)
            .values(
                id=item.id,
                parent_id=parent_id,
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
        connection.execute(
            sa.text(
                """
                UPDATE geographic_areas
                SET name = :name,
                    name_translations = CAST(:translations AS jsonb),
                    level = 'neighbourhood',
                    active = true,
                    display_order = :display_order,
                    lat = :lat,
                    lng = :lng
                WHERE id = :id
                """
            ),
            {
                "id": item.id,
                "name": item.name,
                "translations": json.dumps(
                    {"en": item.name, "zh-HK": item.name_zh},
                    ensure_ascii=False,
                ),
                "display_order": item.display_order,
                "lat": item.lat,
                "lng": item.lng,
            },
        )
        if old_id is not None:
            _repoint_area(connection, old_id, item.id)


def _rename_name_collision(connection, parent_id, name: str, new_id):
    """Free the unique (parent, name) slot before the catalog row is inserted."""
    existing = connection.execute(
        sa.text(
            """
            SELECT id FROM geographic_areas
            WHERE parent_id = :parent AND name = :name
            """
        ),
        {"parent": parent_id, "name": name},
    ).first()
    if existing is None or str(existing[0]) == str(new_id):
        return None
    connection.execute(
        sa.text("UPDATE geographic_areas SET name = :temp WHERE id = :id"),
        {"temp": f"{name} __replaced", "id": existing[0]},
    )
    return existing[0]


def _repoint_area(connection, old_id, new_id) -> None:
    connection.execute(
        sa.text("UPDATE locations SET area_id = :new WHERE area_id = :old"),
        {"new": new_id, "old": old_id},
    )
    connection.execute(
        sa.text("UPDATE geographic_areas SET parent_id = :new WHERE parent_id = :old"),
        {"new": new_id, "old": old_id},
    )
    connection.execute(
        sa.text(
            """
            UPDATE location_fix_proposals
            SET proposed_location = jsonb_set(
                proposed_location, '{area_id}', to_jsonb(CAST(:new AS text)), false
            )
            WHERE proposed_location->>'area_id' = CAST(:old AS text)
            """
        ),
        {"new": str(new_id), "old": str(old_id)},
    )
    connection.execute(
        sa.text("DELETE FROM geographic_areas WHERE id = :id"),
        {"id": old_id},
    )


def _translate_districts(connection: sa.Connection) -> None:
    _rows, _one, _many, district_zh, country_zh = _catalog()
    for name, zh in district_zh.items():
        connection.execute(
            sa.text(
                """
                UPDATE geographic_areas AS district
                SET name_translations = jsonb_set(
                    COALESCE(district.name_translations, '{}'::jsonb),
                    '{zh-HK}',
                    to_jsonb(CAST(:zh AS text)),
                    true
                )
                FROM geographic_areas region
                JOIN geographic_areas country ON region.parent_id = country.id
                WHERE district.parent_id = region.id
                  AND district.level = 'district'
                  AND district.name = :name
                  AND country.code = 'HK'
                  AND COALESCE(district.name_translations->>'zh-HK', '') = ''
                """
            ),
            {"zh": zh, "name": name},
        )
    connection.execute(
        sa.text(
            """
            UPDATE geographic_areas
            SET name_translations = jsonb_set(
                COALESCE(name_translations, '{}'::jsonb),
                '{zh-HK}',
                to_jsonb(CAST(:zh AS text)),
                true
            )
            WHERE code = 'HK'
              AND level = 'country'
              AND COALESCE(name_translations->>'zh-HK', '') = ''
            """
        ),
        {"zh": country_zh},
    )


def _snap(connection, area_id, lat, lng):
    """Nearest neighbourhood id under a non-leaf, plus whether to trust it."""
    row = connection.execute(
        sa.text(
            """
            SELECT id, name, level,
                   EXISTS (
                       SELECT 1 FROM geographic_areas child
                       WHERE child.parent_id = geographic_areas.id
                   ) AS has_children
            FROM geographic_areas
            WHERE id = CAST(:id AS uuid)
            """
        ),
        {"id": area_id},
    ).first()
    if row is None or not row.has_children:
        return (None if row is None else row.id), True
    neighbourhoods, assign_in_district, assign_among, *_rest = _catalog()
    lat_f = None if lat is None else float(lat)
    lng_f = None if lng is None else float(lng)
    if row.level == "district":
        assigned = assign_in_district(row.name, lat_f, lng_f)
    else:
        district_rows = connection.execute(
            sa.text(
                """
                WITH RECURSIVE under AS (
                    SELECT id, name, level
                    FROM geographic_areas
                    WHERE parent_id = :id
                    UNION ALL
                    SELECT child.id, child.name, child.level
                    FROM geographic_areas child
                    JOIN under parent ON child.parent_id = parent.id
                )
                SELECT name FROM under WHERE level = 'district'
                """
            ),
            {"id": area_id},
        ).all()
        names = {item[0] for item in district_rows}
        assigned = assign_among(
            [item for item in neighbourhoods if item.district in names],
            lat_f,
            lng_f,
        )
    if assigned is None:
        return None, False
    found = connection.execute(
        sa.text(
            """
            SELECT neighbourhood.id
            FROM geographic_areas neighbourhood
            JOIN geographic_areas district
              ON neighbourhood.parent_id = district.id
            WHERE neighbourhood.level = 'neighbourhood'
              AND neighbourhood.name = :name
              AND district.name = :district
            LIMIT 1
            """
        ),
        {
            "name": assigned.neighbourhood.name,
            "district": assigned.neighbourhood.district,
        },
    ).first()
    if found is None:
        return None, False
    return found[0], assigned.confident


def _backfill_locations(connection: sa.Connection) -> None:
    rows = connection.execute(
        sa.text(
            """
            SELECT location.id, location.org_id, location.address,
                   location.lat, location.lng, location.area_id
            FROM locations location
            JOIN geographic_areas area ON area.id = location.area_id
            WHERE EXISTS (
                SELECT 1 FROM geographic_areas child
                WHERE child.parent_id = area.id
            )
            """
        )
    ).all()
    for location_id, org_id, address, lat, lng, area_id in rows:
        snapped, confident = _snap(connection, area_id, lat, lng)
        if snapped is None:
            msg = f"No neighbourhood for location {location_id}"
            raise RuntimeError(msg)
        connection.execute(
            sa.text("UPDATE locations SET area_id = :area WHERE id = :id"),
            {"area": snapped, "id": location_id},
        )
        if confident:
            continue
        source = (
            "rule:missing_coordinates"
            if lat is None or lng is None
            else "rule:pin_outside_area"
        )
        rationale = (
            "Neighbourhood was assigned without a close map pin and needs review"
        )
        proposed = json.dumps(
            {
                "address": address or "",
                "area_id": str(snapped),
                "lat": None if lat is None else float(lat),
                "lng": None if lng is None else float(lng),
                "assignment": _ASSIGNMENT,
            }
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO location_fix_proposals (
                    id, entity_type, entity_id, org_id, kind,
                    target_location_id, proposed_location, source,
                    rationale, status
                )
                SELECT gen_random_uuid(), 'location', :location_id, :org_id,
                       'update_location', :location_id,
                       CAST(:proposed AS jsonb),
                       :source, :rationale, 'pending'
                WHERE NOT EXISTS (
                    SELECT 1 FROM location_fix_proposals pending
                    WHERE pending.entity_type = 'location'
                      AND pending.entity_id = :location_id
                      AND pending.status = 'pending'
                )
                """
            ),
            {
                "location_id": location_id,
                "org_id": org_id,
                "proposed": proposed,
                "source": source,
                "rationale": rationale,
            },
        )


def _rewrite_proposals(connection: sa.Connection) -> None:
    rows = connection.execute(
        sa.text(
            """
            SELECT id, proposed_location
            FROM location_fix_proposals
            WHERE proposed_location ? 'area_id'
            """
        )
    ).all()
    for proposal_id, proposed in rows:
        if not isinstance(proposed, dict):
            continue
        area_id = proposed.get("area_id")
        if not area_id:
            continue
        snapped, _confident = _snap(
            connection, area_id, proposed.get("lat"), proposed.get("lng")
        )
        if snapped is None or str(snapped) == str(area_id):
            continue
        proposed = dict(proposed)
        proposed["area_id"] = str(snapped)
        connection.execute(
            sa.text(
                """
                UPDATE location_fix_proposals
                SET proposed_location = CAST(:proposed AS jsonb)
                WHERE id = :id
                """
            ),
            {
                "id": proposal_id,
                "proposed": json.dumps(proposed),
            },
        )


def _leaf_triggers() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION locations_area_must_be_leaf()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.area_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM geographic_areas WHERE parent_id = NEW.area_id
            ) THEN
                RAISE EXCEPTION 'area_id must be a leaf';
            END IF;
            RETURN NEW;
        END;
        $$;

        CREATE TRIGGER locations_area_leaf
        BEFORE INSERT OR UPDATE OF area_id ON locations
        FOR EACH ROW
        EXECUTE FUNCTION locations_area_must_be_leaf();

        CREATE OR REPLACE FUNCTION geographic_area_parent_unused()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.parent_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM locations WHERE area_id = NEW.parent_id
            ) THEN
                RAISE EXCEPTION 'area_id must be a leaf';
            END IF;
            RETURN NEW;
        END;
        $$;

        CREATE TRIGGER geographic_area_parent_unused
        BEFORE INSERT OR UPDATE OF parent_id ON geographic_areas
        FOR EACH ROW
        EXECUTE FUNCTION geographic_area_parent_unused();
        """
    )


def upgrade() -> None:
    """Insert neighbourhoods and move every non-leaf location onto one."""
    op.add_column(
        "geographic_areas",
        sa.Column("lat", sa.Numeric(9, 6), nullable=True),
    )
    op.add_column(
        "geographic_areas",
        sa.Column("lng", sa.Numeric(9, 6), nullable=True),
    )
    connection = op.get_bind()
    _insert_neighbourhoods(connection)
    _translate_districts(connection)
    _backfill_locations(connection)
    _rewrite_proposals(connection)
    _leaf_triggers()


def downgrade() -> None:
    """Point locations at the parent district and delete neighbourhoods."""
    op.execute("DROP TRIGGER IF EXISTS locations_area_leaf ON locations")
    op.execute(
        "DROP TRIGGER IF EXISTS geographic_area_parent_unused ON geographic_areas"
    )
    op.execute("DROP FUNCTION IF EXISTS locations_area_must_be_leaf()")
    op.execute("DROP FUNCTION IF EXISTS geographic_area_parent_unused()")
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM location_fix_proposals
            WHERE status = 'pending'
              AND proposed_location->>'assignment' = :assignment
            """
        ),
        {"assignment": _ASSIGNMENT},
    )
    neighbourhoods, *_rest = _catalog()
    ids = [item.id for item in neighbourhoods]
    parent_id = (
        sa.select(GEO_AREAS.c.parent_id)
        .where(GEO_AREAS.c.id == sa.column("area_id"))
        .scalar_subquery()
    )
    locations = sa.table(
        "locations",
        sa.column("area_id", postgresql.UUID(as_uuid=True)),
    )
    connection.execute(
        sa.update(locations)
        .where(locations.c.area_id.in_(ids))
        .values(area_id=parent_id)
    )
    connection.execute(sa.delete(GEO_AREAS).where(GEO_AREAS.c.id.in_(ids)))
    op.execute("ALTER TABLE geographic_areas DROP COLUMN IF EXISTS lng")
    op.execute("ALTER TABLE geographic_areas DROP COLUMN IF EXISTS lat")
