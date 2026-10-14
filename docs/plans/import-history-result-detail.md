# Plan: Import history result detail

**Status**: Done
**Zone**: yellow

## Goal

On Imports → History, the expanded row explains the job without a
duplicate organization summary. Results load from
`GET /v1/admin/imports/{job_id}` and group by organization, location,
activity, pricing, and schedule. Categories captured always show, with
an em dash when the count is zero. The table and accordion both say
**First recorded**; the accordion says **Last changed** for
`updated_at`.

## Non-goals

- Removing the Organizations table column.
- Persisting category names on the job, or changing the import API
  contract.
- Changing Mode, retry, View orgs, or the file download link.

## Files

- `docs/plans/import-history-result-detail.md`
- `apps/admin_web/src/lib/import-job-results.ts`
- `apps/admin_web/tests/lib/import-job-results.test.ts`
- `apps/admin_web/src/lib/api-client-imports.ts`
- `apps/admin_web/src/lib/api-client.ts`
- `apps/admin_web/src/lib/admin-query-keys.ts`
- `apps/admin_web/src/lib/api-client-org-review.ts`
- `apps/admin_web/src/hooks/use-import-job.ts`
- `apps/admin_web/src/components/admin/org-review/import-history-panel.tsx`
- `apps/admin_web/e2e/org-review.spec.ts`
- `apps/admin_web/e2e/expanded-field-titles.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`

## Invariants this change preserves

- Dry runs still say `Dry run`. Live completed jobs still say
  `Live execution` (and `· skip existing` when updates were off).
- The Organizations table column still shows created/updated counts,
  and appends captured categories when that count is above zero.
- Each result type previews 20 rows, failed first, with Show all for the rest.
- A settled suggestion shows its created name and the captured label.
- A finished job is not refetched on window focus. A running job refreshes
  every 5 seconds.
- File still opens from the expanded row without collapsing it.
- Retry failed still posts the stored `allow_updates` flag.
- A zero or missing `captured_categories` count shows `—`, not a hidden
  field.

## Done when

- `npm test -- tests/lib/import-job-results.test.ts` in `apps/admin_web`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/org-review.spec.ts e2e/expanded-field-titles.spec.ts` in `apps/admin_web`

## Rollback

Revert the branch. No schema change.

## Open questions

None. Category names resolve from suggestion ids on the stored job
when those rows still exist.
