# Plan: listings stop at age 18

**Status**: Draft
**Zone**: yellow

## Goal

A listing's maximum age is 18. Create, update, import, and enrichment
apply reject a higher maximum. The admin form shows the same limit.

## Non-goals

No database constraint. Search filters still accept an older wanted
age. Existing rows are corrected through the partner API, not a
migration.

## Files

- `backend/src/app/api/admin_resource_activity.py`
- `backend/src/app/services/enrichment/apply_rows.py`
- `docs/api/admin.yaml`
- `apps/admin_web/src/types/api-admin.generated.ts`
- `apps/admin_web/src/components/shared/activities-panel.tsx`
- `apps/admin_web/src/components/admin/organization-enrichment-proposals.tsx`
- `tests/test_admin_validation.py`
- `tests/test_listing_kinds.py`
- `tests/test_org_enrichment.py`

## Invariants this change preserves

`age_min` stays at least 0 and still has to be lower than `age_max`.
Import still defaults a missing maximum to 18. Search `age_max` is a
filter, not a stored listing age.

## Done when

`pytest tests/test_admin_validation.py tests/test_listing_kinds.py tests/test_org_enrichment.py`
passes. `npm run generate:api` in `apps/admin_web` leaves no further
diff. Admin `npm run lint` and `npm run typecheck` pass.

## Rollback

Revert the commit. Rows already set to 18 stay at 18.

## Open questions

None. The ceiling replaces the old maximum of 120 on every write that
stores a listing age.
