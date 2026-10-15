# Plan: Catalog import column shows the import time

**Status**: Accepted
**Zone**: yellow

## Goal

On the Catalog table, rename **Import job** to **Import** and show
the organization's import time (`last_imported_at`) instead of the
import job id.

## Non-goals

- Changing the `?job=` catalog filter or the import-job id stored on
  the organization.
- Adding the import job's `created_at` to the org-review payload.
- Changing Imports · History, which still lists each job's created
  time under Timestamp.

## Files

- `docs/plans/catalog-import-column-timestamp.md`
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`
- `apps/admin_web/e2e/organizations.spec.ts`
- `apps/admin_web/e2e/table-cell-captions.spec.ts`

## Invariants this change preserves

- Catalog columns stay Name, Source, Review, Import, Missing, and
  Complete. Source and Review stay secondary. Import, Missing, and
  Complete stay tertiary and repeat under the name while hidden.
- An organization with no import time shows an em dash. On a phone
  the caption is `Import —`.
- Sort by recently imported still sends `sort=last_imported_at`.

## Done when

- Playwright catalog specs assert the header is **Import**, the cell
  shows the formatted `last_imported_at`, and the job id is gone.
- A never-imported row shows the empty caption.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.

## Rollback

Revert the pull request.

## Open questions

None. The cell uses `last_imported_at`, which a live import stamps on
create and on update. The creating job's `created_at` can be earlier
after a later import, and it is empty whenever `import_job_id` is
empty. The catalog column follows the time the organization was
imported.
