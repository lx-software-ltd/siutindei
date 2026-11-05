# Plan: Location label fixes

**Status**: Implemented
**Zone**: yellow

## Goal

Fix the review findings on the optional venue label. An older
location version shows an empty name when that version has no name
key. Pricing, Schedules, and the location dropdown add the address
when the same name is used more than once. An import that changes
other location fields does not warn that a label edit was
overwritten. Folding two venues in an organization merge keeps a
label when the surviving venue has none. The Name input stops at
200 characters. A create request may send null for the label.

## Non-goals

- A uniqueness constraint on the label.
- Showing the label on the Locations list, map pins, or exports.
- Changing how import JSON maps `name` onto the address.

## Files

- `backend/src/app/services/catalog_version_shape.py`
- `backend/src/app/services/org_merge_children.py`
- `docs/api/admin.yaml`
- `apps/admin_web/src/types/api-admin.generated.ts`
- `apps/admin_web/src/lib/location-label.ts`
- `apps/admin_web/src/components/admin/catalog-version-snapshot.ts`
- `apps/admin_web/src/components/shared/locations-panel.tsx`
- `apps/admin_web/src/components/shared/pricing-panel.tsx`
- `apps/admin_web/src/components/shared/schedules-panel.tsx`
- `apps/admin_web/src/components/shared/catalog-inline-editor.tsx`
- `tests/test_location_name.py`
- `tests/test_catalog_versions_compare.py`
- `tests/test_org_merge.py`
- `apps/admin_web/tests/lib/location-label.test.ts`
- `apps/admin_web/tests/components/admin/version-history.test.tsx`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`
- `apps/admin_web/e2e/locations.spec.ts`
- `apps/admin_web/e2e/pricing.spec.ts`
- `apps/admin_web/e2e/schedules.spec.ts`

## Invariants this change preserves

- The address stays the import key and the uniqueness key.
- Import `name` is still written to `address` and does not set or
  clear the label.
- Version history still stores the label. Import comparison ignores
  it, because an import cannot write it.
- A blank label is stored as null. Two venues may share a label.
- Seed rows do not change.

## Done when

`pytest tests/test_location_name.py tests/test_catalog_versions_compare.py tests/test_org_merge.py` passes.
Admin lint, typecheck, the location-label and version-history unit
tests, and the locations, pricing, and schedules Playwright specs pass.

## Rollback

Revert the commit. No migration. The label column stays.

## Open questions

None.
