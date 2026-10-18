# Plan: Data quality after enrichment apply

**Status**: Done
**Zone**: red for the trigger check, yellow for the run, API, and admin UI

## Goal

After an admin applies at least one website-enrichment proposal, stage
a data-quality run with the same Imports settings a live import uses,
scoped to that organization and any activities this apply created.

## Non-goals

- Running checks when a crawl finishes, or when proposals are dismissed.
- Name cleanup, translations, or category-suggestion enrichment.
- The location sweep. That path already is data quality.
- Changing which checks an import runs, or the manual Run checks form.
- A new settings row. The existing Imports settings are the quality-run
  settings.

## Files

- `backend/db/alembic/versions/0057_dq_enrich_trigger.py`
- `backend/src/app/db/models/import_settings.py`
- `backend/src/app/services/data_quality/runs.py`
- `backend/src/app/services/data_quality/scope.py`
- `backend/src/app/services/enrichment/apply.py`
- `backend/src/app/api/admin_enrichment.py`
- `docs/api/admin.yaml`, generated admin types
- `docs/architecture/data-quality.md`, `database-schema.md`, `lambdas.md`
- Imports settings copy and the enrichment apply result

## Invariants this change preserves

- An apply that saves nothing, and a dismiss, enqueue nothing.
- With the default settings row, apply behaviour is unchanged.
- One proposal failing still does not undo the proposals that saved.
- Importers still cannot apply proposals or start runs.
- A second apply while the first run is open creates a second run.
- A missing queue or a failed send leaves the run queued and does not
  fail the apply.
- A contact-only apply does not queue Locations or Categories.
- Locations runs when the apply saved a venue or an activity.
- Categories runs only for activities this apply created.
- A failure while staging the run does not undo proposals that saved.
- A busy check is queued again up to twice, ten minutes apart, before
  it is marked busy.

## Done when

- `pytest tests/test_alembic_revision_contract.py tests/test_org_enrichment.py tests/test_data_quality_engine.py`
- `python3 scripts/check_openapi_routes.py`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Admin vitest for the settings sentence, and the organizations
  Playwright apply flow
- `pre-commit run ruff-format --all-files` before the Python commit

## Rollback

Revert the branch. Downgrade `0057` deletes rows whose trigger is
`enrichment` and restores the old check. Proposals already applied
stay applied. No seed change.

## Open questions

None. Names stay on the import write path. A phone-only apply runs
Duplicates when that check is on, and skips Locations and Categories.
