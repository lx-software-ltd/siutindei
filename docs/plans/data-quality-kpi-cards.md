# Plan: Data quality KPI cards

**Status**: Active
**Zone**: yellow

## Goal

Replace the Names, Locations, and Categories (data quality) count
lines with `AdminKpiCard` tiles above the table card, matching
Catalog and Categories · Suggestions.

- Names: Pending
- Locations: Pending, plus Sweep while a run is active
- Categories: Waiting and Auto-assigned, plus Sweep while a run is
  active

Scope notes, banners, and table cards stay as they are. Duplicates
and Deleted have no count line.

## Non-goals

- Changing summary APIs or sweep / decide behavior
- Putting scope notes or banners inside KPI tiles
- Adding unused breakdowns (`pending_by_entity`, `pending_by_kind`)

## Files

- `apps/admin_web/src/components/admin/data-quality/names-panel.tsx`
- `apps/admin_web/src/components/admin/data-quality/locations-panel.tsx`
- `apps/admin_web/src/components/admin/category-suggestions/category-checks-panel.tsx`
- Unit tests for those panels
- `apps/admin_web/e2e/table-card.spec.ts`
- `apps/admin_web/e2e/data-quality.spec.ts`
- `apps/admin_web/e2e/category-suggestions.spec.ts`

## Invariants this change preserves

- Lists still load, expand, sweep, and decide as today.
- Organization scope notes stay above the table card with Show all.
- KPI chrome matches Catalog (`AdminKpiCard`, three-column grid).

## Done when

- Unit tests assert the KPI labels and values, and the old prose is
  gone.
- Playwright asserts the tiles on Names, Locations, and Categories
  before the table.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- Browser check: each tab shows the tiles, then the table.

## Rollback

Revert the commit.

## Open questions

None.
