# Plan: Import history live-execution label

**Status**: Done
**Zone**: yellow

## Goal

On Imports → History, drop the dedicated File column. The stored
object stays on the row as a line under When, and still opens the
presigned S3 URL without expanding the row. A completed live import
shows the Mode label `Live execution` instead of `completed`.

## Non-goals

- Changing job status in the API or database.
- Removing the File field from the expanded row.
- Changing retry, view-orgs, or the 7-day download URL rules.

## Files

- `apps/admin_web/src/components/admin/org-review/import-history-panel.tsx`
- `apps/admin_web/e2e/org-review.spec.ts`

## Invariants this change preserves

- Dry runs still say `Dry run`.
- Skip-existing live jobs still append `· skip existing`.
- Running and failed live jobs still show their status.
- A row with `download_url` still opens that object without expanding.
- Jobs older than 7 days still show the key without a link.
- Expanded detail still shows File, Mode, and organization counts.

## Done when

- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/org-review.spec.ts` in `apps/admin_web`

## Rollback

Revert the branch. No schema change.

## Open questions

None. Mode is a label over stored `dry_run`, `allow_updates`, and
`status`. The API still returns `completed`.
