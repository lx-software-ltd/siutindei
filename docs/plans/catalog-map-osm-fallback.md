# Plan: Catalog map when Google refuses the admin host

**Status**: Done
**Zone**: yellow

## Goal

Catalog Map still shows every filtered pin when Google Maps refuses
the public website key on the admin host.

## Non-goals

- A new Google Cloud key or a change to the public website key.
  This environment cannot edit that key's allowed websites.
- A new API route.

## Files

- `apps/admin_web/src/lib/catalog-map-surface.ts` chooses Google or OSM.
- `apps/admin_web/src/components/admin/org-review/catalog-org-map.tsx`
  renders OSM when the key is missing or refused.
- `apps/admin_web/tests/catalog-map-surface.test.ts`
- `apps/admin_web/e2e/organizations.spec.ts`

## Invariants this change preserves

- Google Maps is still used when the key accepts this host.
- Pins, Google Maps links, and the Table | Map switch stay the same.
- The table request still does not ask for pins.

## Done when

- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Vitest covers the Google vs OSM choice
- Playwright still covers the neighbourhood map, and a refused key
  still shows the map

## Rollback

Revert the commit. No migration.

## Open questions

None. A human still has to add `https://siutindei.lx-software.com/*`
and `http://localhost:3000/*` to the key if they want Google tiles.
