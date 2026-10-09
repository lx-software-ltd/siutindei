# Plan: Location enrichment from the sweep

**Status**: Accepted
**Zone**: yellow, plus a red migration and the proxy allow-list

## Decisions

1. The sweep loads the EDB school register through `aws_proxy` from
   `www.edb.gov.hk`. `ALLOWED_HTTP_URLS` gains that CSV prefix.
2. Migration `0044_location_enrichment` adds sources `rule:open_data`
   and `lookup:nominatim` and `lookup:google`. No new tables. Lookup
   and register details live in `proposed_location`.
3. A register match with name similarity >= 0.95 is applied during the
   sweep, like `rule:single_location`. At most 200 confident matches
   are created per sweep so the admin request stays inside the API
   Gateway limit. The rest are stored as pending `create_location` and
   the next sweep applies them. Matches from 0.80 up to 0.95 stay
   pending for an admin.
4. Google Place Details (new Places API) is a lookup provider. The key
   is the `GooglePlacesApiKey` CDK parameter (`noEcho`), exposed as
   `GOOGLE_PLACES_API_KEY`. It is sent as `X-Goog-Api-Key`, never in
   the URL, because the proxy logs URLs. An empty key disables the
   provider. Spend uses 0.017 USD per call against the location budget.
5. No one-off production script. Enrichment happens from the Locations
   tab.

## Goal

The Locations sweep matches a venue-less EDB organization to the school
register and can look up pins for `rule:missing_coordinates` in the
background. Nominatim is paced at or under one request per second.
Bulk apply accepts only a precise pin inside the location's district.
Everything else stays for a single apply, a pasted pin, or the CSV
export.

## Non-goals

- Changing the `locations` schema or `activity_locations`.
- District polygons.
- Writing `place_id` from Nominatim.
- A second open-data register.

## Files

- `backend/db/alembic/versions/0044_location_enrichment.py` (red)
- `location_fix_geocode.py`, `location_fix_registers.py`,
  `location_fix_lookup.py`, scan, apply, query, admin and partner
  routes, the category-suggestion worker
- `backend/infrastructure/lib/api-stack.ts` (red: allow-list and key)
- Locations panel, admin OpenAPI, architecture docs

## Invariants this change preserves

- OpenRouter, Nominatim, EDB, and Google are reached only through
  `aws_proxy`. The proxy module itself is unchanged.
- One pending proposal per entity. One active location run.
- A stored pin is never overwritten. `place_id` is never written from
  Nominatim or the register.
- Nominatim stays at or under one request per second across the two
  queue workers (2.2 seconds between calls in one batch).
- No school phone numbers are stored. Tests use fictional schools.

## Done when

`pytest` covers the geocoder, the register, the lookup grades, and
apply guard rails. Admin lint, typecheck, and the Locations panel
tests pass. `python3 scripts/check_openapi_routes.py` passes.

## Rollback

Revert the pull request. Downgrade to `0043` after deleting proposal
rows that use the new sources. Locations and pins already written stay.

## Open questions

None. The Google key is supplied at deploy time; see the pull request.

## Follow-up

Corrections after review are in `docs/plans/location-enrichment-fixes.md`.
