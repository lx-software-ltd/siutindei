# Plan: Import data-quality settings

**Status**: Done
**Superseded by**: `docs/plans/data-quality-engine.md`
**Zone**: yellow

## Goal

Add an Imports **Settings** tab where an admin ticks which Data
quality checks run automatically after a live import: Duplicates,
Names, Locations, and Categories. The same saved flags apply to a
UI import and a board catalog import.

## Non-goals

- A new table or Alembic revision. Settings live in S3 on the existing
  import/export bucket.
- A new API Gateway resource. Read uses `GET /v1/admin/imports/{id}`
  with `id=settings`. Write uses `POST /v1/admin/imports` without
  `object_key`.
- Changing merge, name cleanup during upsert, or category-name
  capture (`on_import_enabled`).
- Running checks on a dry-run.

## Files

- `backend/src/app/services/import_data_quality.py` loads, saves, and
  runs the four checks.
- `backend/src/app/api/admin_imports_settings.py` handles GET/POST
  settings and runs checks after a live import commits.
- `backend/src/app/api/admin_imports.py` dispatches those routes.
- `docs/api/admin.yaml` and generated admin types.
- `docs/architecture/data-quality.md`, `docs/architecture/lambdas.md`,
  and `docs/architecture/admin-web-ui.md`.
- `apps/admin_web` Settings tab, client, Playwright, and unit tests.
- `tests/test_import_data_quality.py`.

## Invariants this change preserves

- Omitting the settings object returns all four flags false, so
  today's import timing stays the same until an admin saves ticks.
- A missing or unreadable settings object does not fail an import.
- A busy or failed sweep does not fail an import that already
  committed.
- `object_key` still starts an import. A settings POST is admin-only.
- Importer JWTs still cannot export or list jobs.
- Dry-run does not start Data quality.

## Done when

- `pytest tests/test_import_data_quality.py tests/test_admin_import_auth.py`
- `python3 scripts/check_openapi_routes.py`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/imports.spec.ts` in `apps/admin_web`
- `pre-commit run ruff-format --all-files` before the Python commit

## Rollback

Revert the branch. No schema change.

## Open questions

None. Defaults stay off. Sweeps use `review_scope=pending_review`.
