# Plan: Catalog version dropdown and source dividers

**Status**: Revised
**Zone**: yellow

## Goal

Replace the full-width Version field with a compact version switcher.
The latest version stays in the normal editor. An earlier version keeps
that page's layout, fills it from the snapshot, and locks it. Changed
fields are marked against the latest snapshot. Treat a missing version
as 1. History stays removed. Organization source fields stay between
the two dividers.

Placement: the organization switcher sits in the card title and the
workspace badge reads `Organization Version N`. Media puts the switcher in the Media
card title. Locations, activities, pricing, and schedules put it in the
editor action bar, and the open row shows an amber version mark.
Removed records move to the Readiness card.

## Non-goals

- Changing catalog version APIs or snapshot shape
- Time-travel GET on live catalog resources
- Manager access to admin version history (managers keep a static
  Version pill for the current version)

## Files

- `docs/plans/catalog-version-dropdown.md`
- `apps/admin_web/src/components/admin/version-history.tsx`
- `apps/admin_web/src/components/admin/catalog-version-snapshot.ts`
- `apps/admin_web/src/components/ui/admin-field-grid.tsx`
- `apps/admin_web/src/components/shared/organizations-panel.tsx`
- `apps/admin_web/src/components/admin/media-panel.tsx`
- `apps/admin_web/src/components/shared/locations-panel.tsx`
- `apps/admin_web/src/components/shared/activities-panel.tsx`
- `apps/admin_web/src/components/shared/pricing-panel.tsx`
- `apps/admin_web/src/components/shared/schedules-panel.tsx`
- `apps/admin_web/tests/components/admin/version-history.test.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`
- `apps/admin_web/e2e/media.spec.ts`
- `apps/admin_web/e2e/manager-dashboard.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`

## Invariants this change preserves

- Live edits still write a new version; historical snapshots stay
  read-only
- Managers still cannot open History or forget removed records
- Organization forget-removed-records still works without History
- Table columns still omit Version; the switcher lives in the editor
- Source fields stay admin-only

## Done when

- Version is a compact switcher of every stored version (missing
  version is 1), default latest
- Selecting a previous version keeps the page layout, fills it from
  the snapshot, locks it, and marks fields that differ from latest
- History disclosure is gone
- Removed records sit on the Readiness card
- Organization source fields sit between two full-width dividers
- `npx vitest run tests/components/admin/version-history.test.tsx`
  and the updated Playwright specs pass
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
