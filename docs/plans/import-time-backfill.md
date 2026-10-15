# Plan: Backfill catalog import times from history

**Status**: Accepted
**Zone**: red

The user asked to fill empty Catalog Import cells from history.
`backend/db/**` is red. This plan is the record of that request.

## Goal

An organization with no `last_imported_at` receives the latest time
from import history. History is a catalog version written by an
import, including a child row, or a completed live job result whose
organization status is `created`, `updated`, `skipped`, or
`unchanged`. A merged-away id fills the survivor. A stored time stays.
`import_job_id` is filled only when it is null and history records
that a job created the organization. `updated_at` and `version` stay
put. A second run changes nothing.

## Non-goals

- Replacing a time a live import already stored.
- Treating a dry run, a failed job, or a failed result as an import.
- Setting `import_job_id` from a skipped, unchanged, or child-only
  import.
- An ops script. The revision runs on upgrade.

## Files

- `docs/plans/import-time-backfill.md`
- `docs/architecture/database-schema.md`
- `backend/db/alembic/versions/0052_import_time_backfill.py`
- `tests/test_import_time_backfill.py`

## Invariants this change preserves

- No new column, constraint, or index. `seed_data.sql` is unchanged.
- `last_imported_at` and `import_job_id` stay outside catalog version
  tracking, so the update does not bump `version` or `updated_at`.
- Downgrade is a no-op. A later live import stores the same columns,
  so a reverse update cannot tell the backfill apart.

## Done when

- `pytest tests/test_alembic_revision_contract.py` from `backend/`
- `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/backend_test pytest tests/test_import_time_backfill.py` from `backend/`
- `pre-commit run ruff-format --all-files` and `pre-commit run ruff --all-files`

## Rollback

Revert the revision before it is applied. After it is applied,
`downgrade` leaves the filled times in place.

## Open questions

None. A job result with no organization id, and no catalog version
that names the organization, still cannot be recovered.
