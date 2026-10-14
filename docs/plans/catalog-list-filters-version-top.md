# Plan: Drop list filters; put version control top-right

**Status**: Done
**Zone**: yellow

## Goal

Locations, activities, pricing, and schedules list every row with no
search bar. The version switcher sits at the top-right of the expanded
editor, not in the action bar.

## Non-goals

- Catalog, data-quality, audit, or review-queue filters
- Organization and media title accessories
- Version APIs or snapshot behaviour

## Files

- `docs/plans/catalog-list-filters-version-top.md`
- `apps/admin_web/src/components/ui/admin-editor-panel.tsx`
- `apps/admin_web/src/components/shared/locations-panel.tsx`
- `apps/admin_web/src/components/shared/activities-panel.tsx`
- `apps/admin_web/src/components/shared/pricing-panel.tsx`
- `apps/admin_web/src/components/shared/schedules-panel.tsx`
- `apps/admin_web/tests/components/ui/admin-table-first.test.tsx`
- `apps/admin_web/e2e/table-card.spec.ts`
- `apps/admin_web/e2e/locations.spec.ts`
- `apps/admin_web/e2e/activities.spec.ts`
- `apps/admin_web/e2e/pricing.spec.ts`
- `apps/admin_web/e2e/schedules.spec.ts`

## Invariants this change preserves

- Create still sits on the table `actions` row
- Historical snapshots stay read-only; latest stays editable
- Table columns still omit Version
- Managers still see a static version pill, not a dropdown
- Other admin lists keep their filters

## Done when

- The four pages have no `AdminFilterBar`
- An expanded existing row shows the version switcher in
  `admin-editor-accessory`, right-aligned above the fields
- Create / Update stay on the editor action bar
- `npx vitest run tests/components/ui/admin-table-first.test.tsx`
- Playwright: `table-card`, `locations`, `activities`, `pricing`,
  `schedules`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
