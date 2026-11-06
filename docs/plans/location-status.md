# Plan: Location status

**Status**: Approved
**Zone**: red

The column is added in `backend/db`. Existing rows become `open`.
Imports do not write the field.

## Goal

Each location is Open, Temporarily Closed, or Permanently Closed.
The stored values are `open`, `temporarily_closed`, and
`permanently_closed`. `open` is the default. The admin location
editor shows a dropdown on the same row as Name, after Name.

## Non-goals

- A status column on the Locations list.
- Import or export JSON.
- Public search, the public website, and the Flutter app.
- Hiding closed venues from search.

## Files

- `backend/db/alembic/versions/0062_location_status.py`
- `backend/src/app/db/models/location.py`
- `backend/src/app/api/admin_resource_location.py`
- `backend/src/app/services/catalog_version_payload.py`
- `backend/src/app/services/catalog_version_shape.py`
- `docs/api/admin.yaml`
- `docs/architecture/database-schema.md`
- `apps/admin_web/src/components/shared/locations-panel.tsx`
- `apps/admin_web/src/components/admin/catalog-version-snapshot.ts`
- `apps/admin_web/src/lib/location-status.ts`
- `apps/admin_web/src/types/api-admin.generated.ts`

## Invariants this change preserves

- Address stays optional and unique within the organization.
- The venue label stays optional and is not an import field.
- Import files do not set or clear status. A reimport keeps it.
- A file that omits status on create stores `open`.
- Seed inserts do not name the new column. The server default fills it.
- Status is not an import-difference field, same as the venue label.

## Done when

`alembic upgrade head` applies `0062_location_status`, then
`backend/db/seed/seed_data.sql` still loads.
`pytest tests/test_location_status.py tests/test_location_name.py tests/test_catalog_versions_compare.py tests/test_alembic_revision_contract.py` passes.
Admin lint, typecheck, the version-history unit test, and the
locations Playwright spec pass.

## Rollback

Downgrade drops `locations_status_check` and `locations.status`.
The API and the admin form treat a missing status as Open, so reads
keep working on the previous column set after the Lambda bundle is
rolled back with the migration.

## Open questions

None. Closed venues stay in public search until a later change.
