"""Allow location-quality proposals on an existing venue.

Revision ID: 0043_location_quality
Revises: 0042_location_fixes

Seed assessment: check constraints only. New entity types, kinds, and
sources are not present in seed_data.sql. Existing proposal rows stay
valid. No seed column, enum, or foreign key changes.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0043_location_quality"
down_revision: Union[str, None] = "0042_location_fixes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENTITY = "entity_type IN ('organization', 'activity', 'location')"
_KIND = "kind IN ('link_existing', 'create_location', 'unresolved', 'update_location')"
_SOURCE = (
    "source IN ("
    "'rule:single_location', 'rule:pricing_schedule', "
    "'rule:name_area', 'rule:no_venue', 'model', "
    "'rule:missing_coordinates', 'rule:empty_address', "
    "'rule:pin_outside_area', 'rule:no_place_id')"
)
_SCAN_ENTITY = (
    "entity_type IS NULL OR entity_type IN ('organization', 'activity', 'location')"
)
_OLD_ENTITY = "entity_type IN ('organization', 'activity')"
_OLD_KIND = "kind IN ('link_existing', 'create_location', 'unresolved')"
_OLD_SOURCE = (
    "source IN ("
    "'rule:single_location', 'rule:pricing_schedule', "
    "'rule:name_area', 'rule:no_venue', 'model')"
)
_OLD_SCAN_ENTITY = "entity_type IS NULL OR entity_type IN ('organization', 'activity')"


def upgrade() -> None:
    _replace("location_fix_proposals", "location_fix_entity_type_check", _ENTITY)
    _replace("location_fix_proposals", "location_fix_kind_check", _KIND)
    _replace("location_fix_proposals", "location_fix_source_check", _SOURCE)
    _replace("location_scan_runs", "location_scan_entity_check", _SCAN_ENTITY)


def downgrade() -> None:
    _replace("location_fix_proposals", "location_fix_entity_type_check", _OLD_ENTITY)
    _replace("location_fix_proposals", "location_fix_kind_check", _OLD_KIND)
    _replace("location_fix_proposals", "location_fix_source_check", _OLD_SOURCE)
    _replace("location_scan_runs", "location_scan_entity_check", _OLD_SCAN_ENTITY)


def _replace(table: str, name: str, expression: str) -> None:
    op.drop_constraint(name, table, type_="check")
    op.create_check_constraint(name, table, expression)
