# Plan: Catalog version dropdown and source dividers

**Status**: Implemented
**Zone**: yellow

## Goal

Replace the History disclosure on organization, media, location,
activity, pricing, and schedule editors with a Version select. The
latest version is the default and stays editable. Choosing an earlier
version loads that snapshot as read-only details. Treat a missing
version as 1. Remove the History control. On the organization form,
draw a visual divider before Source and after Source note.

## Non-goals

- Changing catalog version APIs or snapshot shape
- Time-travel GET on live catalog resources
- Manager access to admin version history (managers keep a Version
  select with the current version only)

## Files

- `docs/plans/catalog-version-dropdown.md`
- `apps/admin_web/src/components/admin/version-history.tsx`
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
- Table columns still omit Version; the select lives in the editor
- Source fields stay admin-only

## Done when

- Version is a select of `1..N` (missing version is 1), default latest
- Selecting a previous version shows that snapshot and hides editor
  actions
- History disclosure is gone
- Organization source fields sit between two full-width dividers
- `npx vitest run tests/components/admin/version-history.test.tsx`
  and the updated Playwright specs pass
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
