# Plan: Organization page heading and Details card

**Status**: Done
**Zone**: yellow

## Goal

The Organization workspace page matches Media and Locations: the
organization name and status badges sit above the card. The card title
is Details. The version switcher sits on the right of that title.

A new organization keeps the outside heading "New organization" with
no badges. An existing organization with no name still uses
"Organization".

## Non-goals

- Catalog table filters or review-queue actions
- Version APIs or snapshot behaviour
- Changing Readiness actions
- Moving `OrganizationWorkspaceTitle` off table workspace pages

## Files

- `docs/plans/org-page-details-header.md`
- `apps/admin_web/src/components/shared/organizations-panel.tsx`
- `apps/admin_web/src/components/ui/card.tsx`
- `apps/admin_web/src/components/admin/organization-readiness.tsx`
- `apps/admin_web/tests/components/ui/admin-input-card.test.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`
- `.cursor/skills/admin-crud-screen/SKILL.md`
- `docs/architecture/admin-web-ui.md`

## Invariants this change preserves

- Create / Update / Merge / Delete stay on the Details card bar
- Historical snapshots stay read-only; latest stays editable
- New organization still has no status badges
- Media and other `titleAccessory` cards also keep the control on the
  right of the title

## Done when

- Existing org: name, operational, and pending review sit above the
  Details card; version switcher is right-aligned on that card
- New organization: outside heading "New organization"; card title
  Details
- `npx vitest run tests/components/ui/admin-input-card.test.tsx tests/components/shared/organization-input-title.test.ts`
- Playwright: `e2e/organizations.spec.ts`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
