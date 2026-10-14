# Plan: Category suggestions KPI cards

**Status**: Active
**Zone**: yellow

## Goal

Replace the Categories · Suggestions count line with three
`AdminKpiCard` tiles above the table card, matching Catalog:

- Pending
- Activities need category
- Spending

The table card stays filters, table, and Load more only.

## Non-goals

- Changing summary API fields or suggestion list behavior
- Adding a spending limit to the tile
- Moving settings into the KPI row

## Files

- `apps/admin_web/src/components/admin/category-suggestions/category-suggestions-panel.tsx`
- `apps/admin_web/src/components/admin/category-suggestions/suggestions-table.tsx`
- `apps/admin_web/e2e/category-suggestions.spec.ts`

## Invariants this change preserves

- Suggestions still load, expand, and decide as today.
- Stranded-activity context still appears when the count is above zero.
- KPI chrome matches Catalog (`AdminKpiCard`, three-column grid).

## Done when

- Playwright asserts the three KPI labels and fixture values before the
  table.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- Browser check: Suggestions shows the tiles, then the table, then
  settings.

## Rollback

Revert the commit.

## Open questions

None.
