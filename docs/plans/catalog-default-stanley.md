# Plan: Catalog default neighbourhood Stanley

The English name constant in this plan was removed. Catalog now
follows `SEARCH_AREA_SCOPE`. See
`docs/plans/2026-11-11-catalog-search-area-scope.md`.

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
  neighbourhood-only lookup.
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
  — Catalog waits for areas, then mounts the list with that default.
  An import-job deep link (`?job=`) skips the default.
- `apps/admin_web/tests/lib/catalog-defaults.test.ts` — lookup helper.
- `apps/admin_web/e2e` — Stanley in the areas mock, a Stanley org, a
  helper that reads the name constant, and request assertions.

## Invariants this change preserves

- Admins can still choose All neighbourhoods or any other leaf.
- Hong Kong neighbourhood ids stay the seeded uuid5 values.
- "View orgs" from import history still lists every org from that job.
- The first catalog list request already includes the default area, so
  the table does not flash the unfiltered set.
- No API or schema change.

## Done when

- Unit tests for `catalog-defaults` pass.
- `npm run lint` and `npm run typecheck` in `apps/admin_web`.
- Playwright covers the Stanley default (org + `area_id` on the first
  list request), import-job links without that area, and the full list
  after clearing the filter.

## Rollback

Revert the commits. No migration.

## Open questions

None.
