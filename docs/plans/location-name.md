# Plan: Location name

**Status**: Approved
**Zone**: red

The column is added in `backend/db`. Existing rows stay null.
The address stays the import key and the uniqueness key.

## Goal

An optional venue label on a location. The admin location editor
shows one Name line before Address. Pricing and Schedules list that
label, and the address when the label is empty.

## Non-goals

- A uniqueness constraint on the label.
- A name column on the Locations list.
- Import or export JSON. Import `name` still means the address.
- Public search, the public website, and the Flutter app.
- Map pins, org review, enrichment, and data-quality labels.

## Files

- `backend/db/alembic/versions/0061_location_name.py`
- `backend/src/app/db/models/location.py`
- `backend/src/app/api/admin_resource_location.py`
- `backend/src/app/api/admin_imports_upsert.py`
- `backend/src/app/services/catalog_version_shape.py`
- `backend/src/app/services/catalog_version_payload.py`
- `docs/api/admin.yaml`
- `docs/architecture/database-schema.md`
- `apps/admin_web/src/components/shared/locations-panel.tsx`
- `apps/admin_web/src/components/shared/pricing-panel.tsx`
- `apps/admin_web/src/components/shared/schedules-panel.tsx`
- `apps/admin_web/src/components/shared/catalog-inline-editor.tsx`
- `apps/admin_web/src/components/admin/catalog-version-snapshot.ts`
- `apps/admin_web/src/lib/location-label.ts`
- `apps/admin_web/src/types/api-admin.generated.ts`

## Invariants this change preserves

- Address stays optional and unique within the organization.
- A blank label is stored as null. Two venues may share a label.
- Import `name` is still written to `address` and does not set or
  clear the label.
- A file that omits the label keeps the stored label.
- Seed inserts do not name the new column.

## Done when

`alembic upgrade head` applies `0061_location_name`, then
`backend/db/seed/seed_data.sql` still loads.
`pytest tests/test_location_name.py tests/test_catalog_versions_compare.py tests/test_catalog_versions_triggers.py tests/test_alembic_revision_contract.py` passes.
Admin lint, typecheck, the location-label unit test, and the
locations, pricing, and schedules Playwright specs pass.

## Rollback

Downgrade drops `locations.name`. The API and the admin form treat
a missing label as empty, so reads keep working on the previous
column set after the Lambda bundle is rolled back with the migration.

## Open questions

None. The label is not unique. The Locations list stays Area and
Address. Import mapping of `name` onto this column is a later change.
