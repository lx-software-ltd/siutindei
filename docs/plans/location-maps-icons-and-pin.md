# Plan: Location map icons and exact pin

**Status**: Implemented
**Zone**: yellow

## Goal

On Locations, the Apple Maps and Google Maps glyphs touch the top
and bottom of the same height. A row with latitude and longitude
opens Google Maps with a pin on those coordinates. The location API
sends coordinates as JSON numbers. The link still accepts the older
decimal strings.

The location editor shows a map under Latitude and Longitude. The
pin sits on those coordinates. Dragging the pin writes them back.
Typing in the fields moves the pin. A closed location or an older
version shows the pin and does not allow a drag.

## Non-goals

- Public website map links.
- Changing how coordinates are stored.

## Files

- `docs/plans/location-maps-icons-and-pin.md`
- `apps/admin_web/src/lib/location-maps.ts`
- `apps/admin_web/tests/lib/location-maps.test.ts`
- `apps/admin_web/src/lib/catalog-map-pins.ts`
- `apps/admin_web/src/components/shared/location-pin-map.tsx`
- `apps/admin_web/src/components/shared/locations-panel.tsx`
- `apps/admin_web/src/types/google-maps.d.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`
- `apps/admin_web/src/components/icons/action-icons.tsx`
- `apps/admin_web/src/components/admin/data-quality/locations-panel.tsx`
- `apps/admin_web/tests/neighbourhood-options.test.ts`
- `apps/admin_web/tests/components/admin/locations-panel.test.tsx`
- `apps/admin_web/e2e/locations.spec.ts`
- `apps/admin_web/e2e/organizations.spec.ts`
- `backend/src/app/api/admin_resource_location.py`
- `tests/test_location_status.py`

## Invariants this change preserves

- Rows without coordinates still open maps by address.
- Map links still open in a new tab.
- Catalog Map still uses the same Google Maps pin URL helper.

## Done when

- `npm test -- tests/lib/location-maps.test.ts tests/neighbourhood-options.test.ts tests/components/admin/locations-panel.test.tsx` in `apps/admin_web`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/locations.spec.ts` in `apps/admin_web`
- `pytest tests/test_location_status.py -k serialized_coordinates`
- Browser: both glyphs touch the top and bottom of one height; Google Maps opens on the stored pin

## Rollback

Revert the pull request.

## Open questions

None.
