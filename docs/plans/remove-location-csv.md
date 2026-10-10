# Plan: Remove location-fix CSV export

**Status**: Accepted
**Zone**: yellow

## Goal

Remove Export CSV from the Locations data-quality tab, and the admin
route that served it.

## Non-goals

- The organization import/export JSON flow
- Name-fix or category export
- Changing sweep, lookup, or apply

## Files

- `apps/admin_web/src/components/admin/data-quality/locations-panel.tsx`
- `apps/admin_web/src/lib/api-client-data-quality.ts`
- `apps/admin_web/tests/components/admin/locations-panel.test.tsx`
- `apps/admin_web/e2e/data-quality.spec.ts`
- `backend/src/app/api/admin_location_fixes.py`
- `docs/api/admin.yaml` and `apps/admin_web/src/types/api-admin.generated.ts`
- `docs/architecture/data-quality.md`

## Invariants this change preserves

- Sweep, lookup, apply, and dismiss stay on the Locations tab
- `text_response` stays; other callers can still emit CSV later
- No PII in source or logs

## Done when

Locations panel tests and the data-quality Playwright spec no longer
expect Export CSV. Admin lint and typecheck pass. A GET of
`/v1/admin/location-fixes/export` is not found.

## Rollback

Revert the pull request.

## Open questions

None.
