"""Fill empty organization import times from history.

Revision ID: 0052_import_time_backfill
Revises: 0051_data_quality_runs

Seed assessment: no schema change. ``seed_data.sql`` does not insert
``organizations`` import times or ``import_jobs``. Existing seed SQL
still runs. No new NOT NULL or CHECK column, no renamed or dropped
column, no new table, and no enum or foreign key used by seed rows
changes.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0052_import_time_backfill"
down_revision: Union[str, None] = "0051_data_quality_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# last_imported_at and import_job_id are outside catalog version
# tracking, so this update does not bump version or updated_at.
BACKFILL_SQL = """
WITH raw_hits AS (
    SELECT
        cv.org_id AS source_id,
        cv.created_at AS imported_at,
        CASE
            WHEN cv.entity_type = 'organization' AND cv.action = 'created'
            THEN cv.import_job_id
            ELSE NULL
        END AS job_id,
        (
            cv.entity_type = 'organization' AND cv.action = 'created'
        ) AS creating
    FROM catalog_versions cv
    WHERE cv.org_id IS NOT NULL
      AND cv.import_job_id IS NOT NULL

    UNION ALL

    SELECT
        (row->>'id')::uuid AS source_id,
        j.created_at AS imported_at,
        CASE
            WHEN row->>'status' = 'created' THEN j.id
            ELSE NULL
        END AS job_id,
        (row->>'status' = 'created') AS creating
    FROM import_jobs j
    CROSS JOIN LATERAL jsonb_array_elements(j.results) AS row
    WHERE j.status = 'completed'
      AND j.dry_run IS FALSE
      AND jsonb_typeof(j.results) = 'array'
      AND row->>'type' = 'organizations'
      AND row->>'status' IN (
          'created', 'updated', 'skipped', 'unchanged'
      )
      AND row->>'id' ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
),
live_hits AS (
    SELECT
        live.id AS org_id,
        raw_hits.imported_at,
        raw_hits.job_id,
        raw_hits.creating
    FROM raw_hits
    JOIN organizations live ON live.id = raw_hits.source_id
),
merged_hits AS (
    SELECT
        walk.survivor_id AS org_id,
        raw_hits.imported_at,
        raw_hits.job_id,
        raw_hits.creating
    FROM raw_hits
    LEFT JOIN organizations live ON live.id = raw_hits.source_id
    JOIN LATERAL (
        WITH RECURSIVE chain AS (
            SELECT
                m.survivor_org_id AS survivor_id,
                1 AS depth
            FROM organization_merges m
            WHERE m.merged_org_id = raw_hits.source_id
              AND m.kind = 'merge'
              AND m.survivor_org_id IS NOT NULL
            UNION ALL
            SELECT
                m.survivor_org_id,
                chain.depth + 1
            FROM chain
            JOIN organization_merges m
              ON m.merged_org_id = chain.survivor_id
             AND m.kind = 'merge'
             AND m.survivor_org_id IS NOT NULL
            WHERE chain.depth < 5
        )
        SELECT chain.survivor_id
        FROM chain
        JOIN organizations survivor ON survivor.id = chain.survivor_id
        ORDER BY chain.depth DESC
        LIMIT 1
    ) walk ON true
    WHERE live.id IS NULL
),
resolved AS (
    SELECT * FROM live_hits
    UNION ALL
    SELECT * FROM merged_hits
),
times AS (
    SELECT org_id, MAX(imported_at) AS imported_at
    FROM resolved
    GROUP BY org_id
),
creators AS (
    SELECT DISTINCT ON (org_id)
        org_id,
        job_id
    FROM resolved
    WHERE creating
      AND job_id IS NOT NULL
      AND EXISTS (
          SELECT 1 FROM import_jobs j WHERE j.id = resolved.job_id
      )
    ORDER BY org_id, imported_at ASC, job_id ASC
)
UPDATE organizations AS org
SET
    last_imported_at = COALESCE(org.last_imported_at, times.imported_at),
    import_job_id = COALESCE(org.import_job_id, creators.job_id)
FROM times
LEFT JOIN creators ON creators.org_id = times.org_id
WHERE org.id = times.org_id
  AND (
      org.last_imported_at IS NULL
      OR (org.import_job_id IS NULL AND creators.job_id IS NOT NULL)
  )
"""


def upgrade() -> None:
    """Fill null import times and creating job ids from history."""
    op.execute(sa.text(BACKFILL_SQL))


def downgrade() -> None:
    """Leave the filled times in place.

    A later live import stores the same columns. Clearing every null
    that this revision filled would also clear those later stamps.
    """
