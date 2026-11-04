# Plan: Catalog default neighbourhood Stanley

**Status**: Done
**Zone**: yellow

## Goal

Open Catalog filtered to Stanley. Keep the default as one English
neighbourhood name constant; Catalog resolves it from the geographic
area tree so a later change is a one-line edit.

## Non-goals

- Changing seeds, the public website wizard, or the search API.
- Persisting the last-used neighbourhood per admin.

## Files

- `docs/plans/catalog-default-stanley.md` — this plan.
- `apps/admin_web/src/lib/catalog-defaults.ts` — the default name and
  lookup helper.
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
  — Catalog applies that default once areas load.
- `apps/admin_web/tests/lib/catalog-defaults.test.ts` — covers the
  constant and lookup helper.
- `apps/admin_web/e2e` — Stanley in the areas mock, clear-to-all helper
  for list assertions, and a default-neighbourhood check.

## Invariants this change preserves

- Admins can still choose All neighbourhoods or any other leaf.
- Hong Kong neighbourhood ids stay the seeded uuid5 values.
- No API or schema change.

## Done when

- Unit tests for `catalog-defaults` pass.
- `npm run lint` and `npm run typecheck` in `apps/admin_web`.
- Playwright covers the Stanley default and still sees the full list
  after clearing the filter.

## Rollback

Revert the commit. No migration.

## Open questions

None.
