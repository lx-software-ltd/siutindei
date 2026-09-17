"""Link orphan activities to a single-location org venue.

Revision ID: 0031_link_orphan_activities
"""

from __future__ import annotations

from typing import Sequence
from typing import Union

from alembic import op

revision: str = "0031_link_orphan_activities"
down_revision: Union[str, None] = "0030_listing_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Activities with no activity_locations row, when the org has exactly
# one location. Seed rows already insert joins with NOT EXISTS, so this
# is a no-op for seed data.
LINK_ORPHAN_ACTIVITIES_SQL = """
INSERT INTO activity_locations (activity_id, location_id)
SELECT a.id, l.id
FROM activities a
JOIN locations l ON l.org_id = a.org_id
WHERE NOT EXISTS (
    SELECT 1
    FROM activity_locations al
    WHERE al.activity_id = a.id
)
AND (
    SELECT COUNT(*)
    FROM locations l2
    WHERE l2.org_id = a.org_id
) = 1
"""


def upgrade() -> None:
    """Backfill activity_locations for single-venue orphan activities."""
    op.execute(LINK_ORPHAN_ACTIVITIES_SQL)


def downgrade() -> None:
    """Keep backfilled joins; they are valid catalog data."""
    return
