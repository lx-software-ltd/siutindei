# Plan: Capitalize Import History Mode values

**Status**: Accepted
**Zone**: yellow

## Goal

On Imports → History, Mode always uses a capitalized label. A live
job whose status is `failed` shows `Failed`, not `failed`. Running
jobs show `Running`. Completed live jobs stay `Live execution`. Dry
runs stay `Dry run`.

## Non-goals

- Changing stored job `status` values or the OpenAPI enum.
- Renaming completed jobs away from `Live execution`.
- Changing result-row StatusBadge copy (`created`, `failed`, and so
  on still use the badge’s own capitalize style).

## Files

- `docs/plans/import-history-mode-capitalize.md`
- `apps/admin_web/src/lib/import-job-results.ts`
- `apps/admin_web/tests/lib/import-job-results.test.ts`
- `apps/admin_web/src/components/admin/org-review/import-history-panel.tsx`
- `apps/admin_web/e2e/org-review.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`

## Invariants this change preserves

- Dry runs still say `Dry run`.
- Completed live jobs still say `Live execution`.
- Skip-existing live jobs still append `· skip existing`.
- Retry, View orgs, Source, and file links stay the same.

## Done when

- Unit tests cover `failed`, `running`, completed, dry run, and skip
  existing.
- Playwright history asserts a `Failed` Mode cell and no exact
  `failed` Mode cell.
- `npm test -- tests/lib/import-job-results.test.ts` in
  `apps/admin_web`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/org-review.spec.ts` in `apps/admin_web`

## Rollback

Revert the branch. No schema change.

## Open questions

None. Mode is a label over stored `dry_run`, `allow_updates`, and
`status`.
