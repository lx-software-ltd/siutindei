# Plan: Location map icons and exact pin

**Status**: Implemented
**Zone**: yellow

## Goal

On Locations, the Apple Maps and Google Maps icons are the same
height. A row with latitude and longitude opens Google Maps with a
pin on those coordinates, including when the API sends them as
strings.

## Non-goals

- An embedded map in the editor.
- Public website map links.
- Changing how coordinates are stored.

## Files

- `docs/plans/location-maps-icons-and-pin.md`
- `apps/admin_web/src/lib/location-maps.ts`
- `apps/admin_web/tests/lib/location-maps.test.ts`
- `apps/admin_web/src/lib/catalog-map-pins.ts`
- `apps/admin_web/src/components/shared/locations-panel.tsx`
- `apps/admin_web/src/components/icons/action-icons.tsx`
- `apps/admin_web/src/components/admin/data-quality/locations-panel.tsx`
- `apps/admin_web/tests/neighbourhood-options.test.ts`
- `apps/admin_web/tests/components/admin/locations-panel.test.tsx`
- `apps/admin_web/e2e/locations.spec.ts`
- `apps/admin_web/e2e/organizations.spec.ts`

## Invariants this change preserves

- Rows without coordinates still open maps by address.
- Map links still open in a new tab.
- Catalog Map still uses the same Google Maps pin URL helper.

## Done when

- `npm test -- tests/lib/location-maps.test.ts tests/neighbourhood-options.test.ts tests/components/admin/locations-panel.test.tsx` in `apps/admin_web`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/locations.spec.ts` in `apps/admin_web`
- Browser: both icons share one height; Google Maps opens on the stored pin

## Rollback

Revert the pull request.

## Open questions

None.
