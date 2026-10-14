# Plan: Backfill import job source

**Status**: Done
**Zone**: red

The user asked for this revision in a new pull request. `backend/db/**`
is red. This plan is the record of that request.

## Goal

Every import job that does not already store `source` `ui` or `board`
on `summary` is labeled `board`. Imports before the source field
existed all came from the Board API. History then shows Board API
instead of an em dash. Jobs that already store `ui` or `board` stay
as they are, including a UI import recorded after the field shipped.
`updated_at` stays unchanged, so Last changed does not move.

## Non-goals

- A new column. `source` stays inside `summary`, the same way
  `allow_updates` does.
- A read-time default. After this revision the database is the source
  of truth. A reader that has not run it still shows an em dash.
- Changing caller detection, OpenAPI, or the history table.
- Relabeling a job that already stores `ui` or `board`.
- Removing `source` on downgrade. A later Board API import stores the
  same value, so a reverse update cannot tell the two apart.

## Files

- `docs/plans/import-history-source-backfill.md`
- `docs/architecture/database-schema.md`
- `backend/db/alembic/versions/0050_import_job_source.py`
- `tests/test_import_job_source_backfill.py`

## Invariants this change preserves

- `summary` stays jsonb. No new NOT NULL, CHECK, or enum.
- `seed_data.sql` does not insert `import_jobs` and does not change.
- The update sets only `summary`. There is no `updated_at` trigger on
  `import_jobs`.
- A non-object `summary` is left alone. `jsonb_set` cannot add an
  object key to an array, and writers store objects.
- Downgrade is a no-op. Older readers ignore the JSON key.

## Done when

- `pytest tests/test_alembic_revision_contract.py` from `backend/`
- `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/backend_test pytest tests/test_import_job_source_backfill.py` from `backend/`
- `alembic upgrade head` then `seed_data.sql` on a fresh database
- `pre-commit run ruff-format --all-files` and `pre-commit run ruff --all-files`

## Rollback

Revert the revision before it is applied. After it is applied,
`downgrade` leaves `source` in place. Reverting the code does not
strip the key. Older readers ignore it.

## Open questions

None.
