# Plan: Catalog map organization link

**Status**: Done
**Zone**: yellow

## Goal

On Catalog → Map, each row in the organization list links to that
organization in the workspace. The pin popup title uses the same link.

## Non-goals

- Changing the Google Maps pin link or the map filters.
- Linking organizations that have no map pin. Those stay in the count
  banner.
- A new API field. The review list already returns the organization id.

## Files

- `docs/plans/catalog-map-org-link.md`
- `apps/admin_web/src/lib/catalog-map-pins.ts`
- `apps/admin_web/tests/neighbourhood-options.test.ts`
- `apps/admin_web/src/components/admin/org-review/catalog-org-map.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`

## Invariants this change preserves

- One list row is still one mapped location. Two locations of the same
  organization stay two rows and both open that organization.
- The Google Maps link still opens in a new tab.
- The table view still opens an organization by selecting the row.
- Neighbourhood, import, and other catalog filters still decide which
  rows appear.

## Done when

- `npm test -- tests/neighbourhood-options.test.ts` in `apps/admin_web`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/organizations.spec.ts` in `apps/admin_web`

## Rollback

Revert the branch. No schema change.

## Open questions

None. The workspace URL is `/admin/dashboard?section=organizations&org=<id>`,
the same link import history already uses.
