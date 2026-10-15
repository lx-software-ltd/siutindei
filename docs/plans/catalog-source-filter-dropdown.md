# Plan: Catalog source filter dropdown

**Status**: Done
**Zone**: yellow

## Goal

The Catalog source filter is a menu of the catalog sources
(`lcsd`, `edb`, `swd`, `places`, `competitor`), with an empty
choice that shows every source. Choosing one filters the table
and the map immediately.

## Non-goals

- Data-quality, suggestion, or import-history source filters
- The organization editor source field
- Changing the review-list API or which strings it accepts
- Relabeling the Source column

## Files

- `docs/plans/catalog-source-filter-dropdown.md`
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`

## Invariants this change preserves

- Empty selection still omits `source` from the review query
- The name filter stays a debounced text field
- Source labels match the organization editor (`LCSD`, `EDB`,
  `SWD`, `Places`, `Competitor`)
- The same filter bar still drives Table and Map

## Done when

- The source control is a select whose options are Any source
  plus the five catalog sources
- Selecting LCSD requests `source=lcsd` and hides other rows
- `npx playwright test e2e/organizations.spec.ts`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
