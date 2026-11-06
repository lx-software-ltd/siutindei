# Plan: Location status

**Status**: Approved
**Zone**: red

The column lives in `backend/db`. The follow-up scope below was
requested after review: server-side lock, public search, export, and
the admin pickers. Managers may set the status.

## Goal

Each location is Open, Temporarily Closed, or Permanently Closed.
The stored values are `open`, `temporarily_closed`, and
`permanently_closed`. `open` is the default. The admin location
editor shows a dropdown on the same row as Name, after Name.

While the status is closed, address, area, latitude, longitude, and
`place_id` stay as stored. Name and status stay editable. The editor
explains that, restores unsaved detail edits when the status becomes
closed, and refuses to close a new location until an area is chosen.
The area column shows a circled cross as soon as the open editor
selects a closed status.

Public search omits `permanently_closed` venues and returns `status`
on the location. Temporarily closed venues stay in the results and
use the existing temporarily-closed badge. Export JSON includes
`status`. A new import stores it. A later import does not change it
and does not rewrite the frozen fields of a closed location.

## Non-goals

- A status column on the Locations list.
- Treating status as an import-difference field.
- Hiding temporarily closed venues from search.

## Files

- `backend/db/alembic/versions/0062_location_status.py`
- `backend/src/app/db/models/location.py`
- `backend/src/app/api/admin_resource_location.py`
- `backend/src/app/api/admin_imports_upsert.py`
- `backend/src/app/api/admin_imports_export.py`
- `backend/src/app/api/search.py`
- `backend/src/app/api/schemas.py`
- `backend/src/app/db/queries.py`
- `backend/src/app/services/catalog_version_payload.py`
- `backend/src/app/services/catalog_version_shape.py`
- `backend/src/app/services/location_fix_apply.py`
- `backend/src/app/services/location_fix_scan.py`
- `backend/src/app/services/location_fix_scan_scope.py`
- `backend/src/app/services/location_fix_model.py`
- `backend/src/app/services/location_fix_query.py`
- `backend/src/app/services/staging_search_store.py`
- `backend/src/app/api/admin_enrichment.py`
- `docs/api/admin.yaml`
- `docs/api/search.yaml`
- `docs/architecture/database-schema.md`
- `apps/admin_web/src/components/shared/locations-panel.tsx`
- `apps/admin_web/src/lib/location-label.ts`
- `apps/public_www/src/lib/activities/`
- `apps/siutindei_app/lib/`

## Invariants this change preserves

- Address stays optional and unique within the organization.
- The venue label stays optional and is not an import field.
- A reimport does not change status. A file that omits status on
  create stores `open`. A file that sets status on create stores it.
- Seed inserts do not name the new column. The server default fills it.
- Status is not an import-difference field, same as the venue label.
- Managers use the same location update as admins and may set status.
- Closing a location does not clear its address or coordinates.

## Done when

`alembic upgrade head` applies `0062_location_status`, then
`backend/db/seed/seed_data.sql` still loads.
`pytest tests/test_location_status.py tests/test_location_name.py tests/test_catalog_versions_compare.py tests/test_catalog_versions_triggers.py tests/test_location_fix_scan.py tests/test_search_text_and_view.py tests/test_alembic_revision_contract.py` passes.
Admin lint, typecheck, the location-label and version-history unit
tests, and the locations Playwright spec pass. Public website lint
and the listing-status unit test pass.

## Rollback

Downgrade drops `locations_status_check` and `locations.status`.
The API and the admin form treat a missing status as Open, so reads
keep working on the previous column set after the Lambda bundle is
rolled back with the migration. Search then has no location status
to filter on, so the previous search behaviour returns.

## Open questions

None. Permanently closed venues leave public search. Temporarily
closed venues stay, with `status` on the location. Managers may
close a venue.
