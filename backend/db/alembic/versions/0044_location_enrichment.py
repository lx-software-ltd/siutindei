"""Allow open-data and pin-lookup sources on venue proposals.

Revision ID: 0044_location_enrichment
Revises: 0043_location_quality

Seed assessment: check constraints only. The new sources
``rule:open_data``, ``lookup:nominatim``, and ``lookup:google`` are
not present in seed_data.sql. Existing proposal rows stay valid. No
seed column, enum, or foreign key changes.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0044_location_enrichment"
down_revision: Union[str, None] = "0043_location_quality"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SOURCE = (
    "source IN ("
    "'rule:single_location', 'rule:pricing_schedule', "
    "'rule:name_area', 'rule:no_venue', 'model', "
    "'rule:missing_coordinates', 'rule:empty_address', "
    "'rule:pin_outside_area', 'rule:open_data', "
    "'lookup:nominatim', 'lookup:google')"
)
_OLD_SOURCE = (
    "source IN ("
    "'rule:single_location', 'rule:pricing_schedule', "
    "'rule:name_area', 'rule:no_venue', 'model', "
    "'rule:missing_coordinates', 'rule:empty_address', "
    "'rule:pin_outside_area')"
)


def upgrade() -> None:
    _replace("location_fix_proposals", "location_fix_source_check", _SOURCE)


def downgrade() -> None:
    _replace("location_fix_proposals", "location_fix_source_check", _OLD_SOURCE)


def _replace(table: str, name: str, expression: str) -> None:
    op.drop_constraint(name, table, type_="check")
    op.create_check_constraint(name, table, expression)
