# Plan: Data quality engine

**Status**: Done
**Zone**: red for the migration, yellow for the engine, API, and admin UI

## Goal

One set of Data quality checks (Names, Duplicates, Locations,
Categories) runs after a live import and on demand. Names during
import defaults to Apply and replaces the hidden name rewrite.
Pending name proposals block organization approval. Settings live
in `import_settings`. Checks are idempotent: a second run on the
same inputs writes nothing. Model and lookup answers are reused
from the recorded reply for the same input.

## Non-goals

- Dropping `category_suggestion_settings.on_import_enabled` in this
  change. Imports read `import_settings`. The old column stays until
  a later revision.
- Making manual Location sweeps asynchronous. Import and Run checks
  use the queue. The existing Sweep buttons keep their response.
- A lifecycle change for the import bucket. Settings are not in S3.

## Files

- `backend/db/alembic/versions/0051_data_quality_runs.py`
- `backend/src/app/db/models/import_settings.py`
- `backend/src/app/services/import_settings.py`
- `backend/src/app/services/data_quality/`
- Import, name, location, and category call sites listed in the
  implementation
- Admin Imports Settings, Data quality Runs, and the approval blocker

## Invariants this change preserves

- With the default row, a live import still applies name cleanup,
  captures unknown categories, skips deleted organizations, and
  forwards merges.
- A dry-run commits nothing and does not enqueue a run.
- A busy or failed check does not fail an import that already
  committed.
- Importer tokens can import and cannot change settings or start runs.

## Done when

- `pytest tests/test_alembic_revision_contract.py tests/test_data_quality_engine.py`
- `pytest tests/test_import_names.py tests/test_category_suggestions.py`
- Admin vitest for the settings panel
- `pre-commit run ruff-format --all-files` before the Python commit

## Rollback

Revert the branch. Downgrade `0051_data_quality_runs` drops the new
tables and columns. It does not restore category reviews that the
upgrade dismissed; those rows stay `dismissed`, with `decided_by`
`migration` and `decided_at` set. No seed change. The upgrade inserts
the `import_settings` singleton.

## Open questions

None. Names default to apply. Pending name proposals block approval.
Settings use `GET` and `PUT /v1/admin/import-settings`. Run checks
ships now. Merge forwarding stays always on.
