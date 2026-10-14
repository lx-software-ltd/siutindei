"""Label historical import jobs as Board API.

Revision ID: 0050_import_job_source
Revises: 0049_catalog_version_fixes

Seed assessment: no schema change. ``import_jobs`` is not inserted by
seed_data.sql. Existing seed SQL still runs. No new NOT NULL or CHECK
column, no renamed or dropped column, no new table, and no enum or
foreign key used by seed rows changes.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0050_import_job_source"
down_revision: Union[str, None] = "0049_catalog_version_fixes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Sets summary.source only. Omitting updated_at keeps Last changed.
BACKFILL_SQL = """
UPDATE import_jobs
SET summary = jsonb_set(
    summary,
    '{source}',
    '"board"'::jsonb,
    true
)
WHERE jsonb_typeof(summary) = 'object'
  AND COALESCE(summary->>'source', '') NOT IN ('ui', 'board')
"""


def upgrade() -> None:
    """Stamp unlabeled import jobs with source board."""
    op.execute(sa.text(BACKFILL_SQL))


def downgrade() -> None:
    """Leave source in place.

    A later Board API import stores the same value. Removing every
    board source would erase those jobs as well as this backfill.
    Older readers ignore the key.
    """
