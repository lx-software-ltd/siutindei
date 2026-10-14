# Plan: Import history source

**Status**: Done
**Zone**: yellow

## Goal

Imports → History shows who started each job. The table columns are
**Timestamp** (renamed from First recorded), **Source**, **Mode**, and
**Operations**. Source is `UI import` for an admin session and
`Board API` for the importer group (the board catalog API). Jobs
stored before this field existed show an em dash. The expanded row
uses the same Timestamp and Source labels.

## Non-goals

- A new `import_jobs` column or Alembic revision. Source is stored on
  the job summary, the same way `allow_updates` is.
- Letting the client send a source. The authorizer decides it, so a
  caller cannot relabel the run.
- Keeping the Changes column. Created and updated counts stay in the
  expanded Results section.
- Changing retry, View orgs, Mode, or the file download link.

## Files

- `docs/plans/import-history-source.md`
- `docs/api/admin.yaml`
- `backend/src/app/api/admin_imports_jobs.py`
- `backend/src/app/api/admin_imports.py`
- `tests/test_import_job_lifecycle.py`
- `apps/admin_web/src/lib/import-job-results.ts`
- `apps/admin_web/tests/lib/import-job-results.test.ts`
- `apps/admin_web/src/lib/api-client-org-review.ts`
- `apps/admin_web/src/lib/api-client-imports.ts`
- `apps/admin_web/src/types/api-admin.generated.ts`
- `apps/admin_web/src/components/admin/org-review/import-history-panel.tsx`
- `apps/admin_web/e2e/org-review.spec.ts`
- `apps/admin_web/e2e/expanded-field-titles.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`

## Invariants this change preserves

- An admin who is also in the importer group is `ui`. That matches the
  import path that clears the board catalog manager.
- A retry keeps the source already stored on the job.
- A failed live import keeps that source on the error summary.
- Dry runs still say `Dry run`. Live completed jobs still say
  `Live execution` (and `· skip existing` when updates were off).
- File still opens from the expanded row without collapsing it.
- Retry failed still posts the stored `allow_updates` flag.
- Idempotent replay of the same object key does not invent a source
  for a job that never stored one.

## Done when

- `pytest tests/test_import_job_lifecycle.py` from `backend/`
- `npm test -- tests/lib/import-job-results.test.ts` in `apps/admin_web`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/org-review.spec.ts e2e/expanded-field-titles.spec.ts` in `apps/admin_web`

## Rollback

Revert the branch. No schema change. Stored summaries may contain
`source`; readers ignore unknown keys.

## Open questions

None. Further callers (the "etc") add a value to the source set, the
OpenAPI enum, and the history label map.
