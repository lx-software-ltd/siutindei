# Plan: Strip import path prefixes from history notes

**Status**: Done
**Zone**: yellow

## Goal

On Imports → History, result notes drop a leading JSON index path
such as `organizations[0]:`. `organizations[0]: ignored flat location
fields…` shows as `ignored flat location fields…`.

## Non-goals

- Changing stored import warnings or the import API.
- Changing the Import form File warnings list.
- Changing Mode, retry, View orgs, or the file download link.

## Files

- `docs/plans/import-history-strip-path-notes.md`
- `apps/admin_web/src/lib/import-job-results.ts`
- `apps/admin_web/tests/lib/import-job-results.test.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`
- `apps/admin_web/e2e/org-review.spec.ts`

## Invariants this change preserves

- Result grouping, badges, and keys stay the same.
- Notes that have no path prefix stay unchanged.
- File still opens from the expanded row without collapsing it.

## Done when

- `npm test -- tests/lib/import-job-results.test.ts` in `apps/admin_web`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/org-review.spec.ts -g "hides JSON index paths"` in `apps/admin_web`

## Rollback

Revert the branch. No schema change.

## Open questions

None.
