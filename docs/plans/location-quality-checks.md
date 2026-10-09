# Plan: Location quality checks

**Status**: Accepted
**Zone**: yellow, plus one red migration under `backend/db/alembic/versions/`

## Goal

Extend the Locations sweep so an existing venue can be fixed, and so an
admin can link one of several model candidates without leaving the row.

- A location with an address and no coordinates becomes
  `update_location` / `rule:missing_coordinates`. The sweep stores the
  address and does not call Nominatim. Apply on one row looks the pin
  up, writes `lat` and `lng` to six decimal places, and leaves
  `place_id` unchanged. Apply does not replace a pin that is already
  stored. Bulk apply does not look pins up.
- Rules only, no model: empty address (`rule:empty_address`) and a pin
  that falls in a different Hong Kong district or outside Hong Kong
  (`rule:pin_outside_area`). The area chain must include Hong Kong.
  Boxes overlap at a shared boundary, so a pin in both boxes is not
  flagged. These stay `unresolved`. One pending row per location,
  highest issue first. A missing Google place id is not a location
  finding.
- An unresolved activity row that lists candidates accepts
  `target_location_id` on apply and creates the same join as
  `link_existing`. The proposal kind stays `unresolved`.

## Non-goals

- Changing `missing_coordinates` or `no_locations` from blockers.
- Filling `place_id` from Nominatim. Location `place_id` stays a Google
  Places id.
- Duplicate-location detection or merging locations.
- Polygons for districts. The pin check uses fixed boxes for the 18
  Hong Kong districts, matched on the area name or a translation.
- Auto-applying geocodes or the new unresolved findings.

## Files

- `backend/db/alembic/versions/0043_location_quality.py` widens the
  check constraints. No `seed_data.sql` change: new allowed values do
  not appear in seed rows, and existing proposal rows stay valid.
- `backend/src/app/db/models/location_fix.py` keeps the same checks for
  local `create_all` tests.
- `location_fix_districts.py`, `location_fix_quality.py` hold the rules.
- Scan, apply, decide, query, OpenAPI, the Locations panel, and
  `docs/architecture/data-quality.md` plus `database-schema.md`.

## Invariants this change preserves

- `rule:single_location` still links immediately. Other activity rules
  stay pending. A dismissed unresolved activity or organization is
  still not sent to the model. A dismissed location finding matches
  the same source, and a dismissed pin also matches the rounded
  coordinates.
- One pending proposal per `(entity_type, entity_id)`.
- Category-check spend is still not counted against the location budget.
- Applying a new sole venue still links activities that have no join.

## Done when

`pytest tests/test_location_fix_quality.py tests/test_location_fix_scan.py tests/test_alembic_revision_contract.py`
passes. Admin `npm run lint`, `npm run typecheck`, and the Locations
Playwright spec pass. `python3 scripts/check_openapi_routes.py` passes.

## Rollback

`alembic downgrade` to `0042_location_fixes` restores the previous
checks. Delete proposal rows that use `location`, `update_location`, or
the new sources first, or the downgrade fails the check.

## Open questions

None.
