# Plan: Organization Version title tag

**Status**: Done
**Zone**: yellow

## Goal

Rename the workspace title version tag from `Org vN` to
`Organization Version N` on Media, Locations, Activities, Pricing, and
Schedules. The string lives in `OrganizationStatusBadges`, which
`OrganizationWorkspaceTitle` renders above those pages.

## Non-goals

- Changing the organization catalog version switcher
- Showing the tag on the Organizations card (that page keeps
  `version='hidden'`)
- Catalog version APIs or snapshot shape

## Files

- `docs/plans/org-version-title-tag.md`
- `docs/plans/catalog-version-dropdown.md`
- `apps/admin_web/src/components/admin/organization-workspace-title.tsx`
- `apps/admin_web/tests/components/admin/organization-workspace-title.test.tsx`
- `apps/admin_web/e2e/media.spec.ts`
- `apps/admin_web/e2e/locations.spec.ts`
- `apps/admin_web/e2e/activities.spec.ts`
- `apps/admin_web/e2e/pricing.spec.ts`
- `apps/admin_web/e2e/schedules.spec.ts`

## Invariants this change preserves

- The tag still appears only when `version === 'org'` and the
  organization has a version
- Status and review badges stay next to the organization name
- Organizations still hides this tag in favor of the version switcher

## Done when

- The title tag reads `Organization Version N`
- Vitest for `OrganizationStatusBadges` and the workspace Playwright
  specs pass
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
