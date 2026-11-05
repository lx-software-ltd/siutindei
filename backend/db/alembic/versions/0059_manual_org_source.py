"""Label unset organization sources as Manual.

Revision ID: 0059_manual_org_source
Revises: 0058_entry_order_idx

Seed assessment: no schema change. ``organizations.source`` stays
nullable free text. Fresh seed inserts Kowloon Kids Dance as
``manual``. Existing seed SQL still runs. No new NOT NULL or CHECK
column, no renamed or dropped column, no new table, and no foreign
key used by seed rows changes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0059_manual_org_source"
down_revision: Union[str, None] = "0058_entry_order_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILL_SQL = """
UPDATE organizations
SET source = 'manual'
WHERE source IS NULL OR btrim(source) = ''
"""


def upgrade() -> None:
    """Stamp unlabeled organizations with source manual."""
    op.execute(sa.text(BACKFILL_SQL))


def downgrade() -> None:
    """Leave source in place.

    A later create or import stores the same value. Removing every
    manual source would erase those rows as well as this backfill.
    Older readers treat unset and manual the same.
    """
