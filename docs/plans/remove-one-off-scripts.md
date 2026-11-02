# Plan: Remove finished one-off scripts

**Status**: Done
**Zone**: yellow (`backend/src/app/services/**`), plus green docs

## Goal

Delete tooling that existed for a single operation that has already
finished, so readers stop treating it as live. Refresh the docs that
pointed at it.

## Non-goals

- Recurring operator tools. `scripts/ops/board-importer` rotates the
  importer password and stays.
- Migration-owned SQL. `backend/db/catalog_version_backfill.sql` is
  loaded by revision `0049` and stays with the Alembic history.
- Developer helpers such as `backend/scripts/prepare_infra_synth_env.sh`.

## Files

- `scripts/ops/backfill_org_websites.py`,
  `backend/src/app/services/import_website_backfill.py`, and
  `tests/test_import_website_backfill.py`. The backfill copied
  websites out of import files that ran before `0047_org_website`
  (#648, 2026-10-13). Imports now store `website` directly and never
  write the "website is accepted but not stored" warning, and import
  files expire after 7 days, so the backfill has nothing left to read.
- `docs/deployment/ops-alarms-stack-refactor.md`. The CloudShell
  runbook for the one-time move of the ops alarms into
  `OpsAlarmsStack`. Stage 3 is on `main` and deployed, and the
  `ops_alarms_refactor.py` script it uses was already deleted.
  `docs/plans/ops-alarms-nested-stack.md` keeps the record.

## Invariants this change preserves

- No runtime module imports the deleted service.
- Catalog imports still write `website`.
- Historical import jobs keep whatever warning text they stored.

## Done when

- `git grep` finds no reference to the deleted files outside
  `docs/plans/`.
- `pytest tests/test_admin_imports.py tests/test_org_review.py`
- `python3 scripts/check_python_file_length.py`,
  `node scripts/check-lambda-docs.mjs`, and
  `python3 scripts/validate_agent_rules.py`
- `pre-commit run ruff-format --all-files`

## Rollback

Revert the commit. The backfill is idempotent, so restoring it is safe.
