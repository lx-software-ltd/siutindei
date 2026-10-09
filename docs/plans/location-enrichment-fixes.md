# Plan: Location enrichment review fixes

**Status**: Accepted
**Zone**: yellow

## Goal

Correct the enrichment sweep so a failed download or lookup is not
treated as a finished result, a proposed pin is not replaced by a
weaker lookup, and Google spend stays inside the remaining monthly
budget.

## Non-goals

- A new migration or a change to the proxy, the allow-list, or deploy
  workflows.
- Reverting the admin address search or the CSV response helper. Those
  stay, and this plan names them.

## Files

- `backend/src/app/services/location_fix_geocode.py`
- `backend/src/app/services/location_fix_registers.py`
- `backend/src/app/services/location_fix_lookup.py`
- `backend/src/app/services/location_fix_scan.py`
- `backend/src/app/services/location_fix_scan_scope.py` (helpers moved
  out of the scan module so it stays under the line limit)
- `backend/src/app/services/location_fix_quality.py`
- `apps/admin_web/src/components/admin/data-quality/locations-panel.tsx`
- `apps/admin_web/src/lib/api-client-data-quality.ts`
- `docs/architecture/data-quality.md`
- `docs/architecture/security.md`
- `docs/architecture/lambdas.md`
- tests for the geocoder, register, lookup, and Locations panel

Already shipped, and kept:

- `apps/admin_web/src/hooks/use-geographic-areas.ts` omits
  `countrycodes` when Hong Kong is an active country, because
  Nominatim files Hong Kong under China.
- `backend/src/app/utils/responses.py` `text_response` carries the
  location CSV export.

## Invariants this change preserves

- A stored `locations` pin is never overwritten. `place_id` is never
  written from Nominatim, Google, or the register.
- One pending proposal per entity. One active location run.
- Nominatim stays at or under one request per second.
- Google is reached only through `aws_proxy`, with the key in
  `X-Goog-Api-Key`.
- No school phone numbers are stored.

## Behavior

- A failed EDB download is not cached. EDB organizations are left for
  the next sweep, and the run records the failure. A successful
  download, including an empty file, is cached.
- Nominatim and Google transport failures are not stored as `miss`.
- Nominatim does not replace a Google pin or a pin an admin pasted.
  Google may replace a Nominatim pin. A stored lookup sets
  `source` to `lookup:nominatim` or `lookup:google`. A later sweep
  keeps that source and pin.
- The 200-create cap does not skip the activity pass. Creates also
  stop once the sweep has used 18 seconds, and the rest stay pending.
- Google lookups are capped to the remaining monthly budget at
  0.017 USD each. The run is truncated when the cap cuts the queue.
- A lookup run that does not scan locations still counts the queued
  venues in `total_entities`.
- The Places key stays a noEcho CloudFormation parameter on the admin
  Lambda. Security docs say it is not in Secrets Manager, and why.

## Done when

`pytest` covers a failed register fetch, the create cap, the time
budget, lookup grades, overwrite protection, the Google budget, and
apply guard rails. Admin lint, typecheck, and the Locations panel
tests pass.

## Rollback

Revert the pull request. Locations and pins already written stay.

## Open questions

None.
