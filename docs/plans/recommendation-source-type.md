# Plan: Recommendation catalog source

**Status**: Done
**Zone**: yellow

## Goal

Add `recommendation` as a catalog organization source, labeled
Recommendation in the admin editor and Catalog source filter.

## Non-goals

- A database CHECK on `organizations.source` (the column stays free
  text; allowed values stay in the API)
- Seed rows that use the new source
- Data-quality, suggestion, import-history, or listing-event sources
- Relabeling existing sources

## Files

- `docs/plans/recommendation-source-type.md`
- `backend/src/app/api/admin_imports_catalog.py`
- `docs/api/admin.yaml`
- `docs/architecture/database-schema.md`
- `apps/admin_web/src/components/shared/organizations/organization-form-utils.tsx`
- `apps/admin_web/src/types/api-admin.generated.ts`
- `tests/test_admin_imports.py`
- `tests/test_org_listing_status.py`
- `apps/admin_web/tests/components/shared/organization-source-options.test.ts`
- `apps/admin_web/e2e/organizations.spec.ts`

## Invariants this change preserves

- Existing sources (`lcsd`, `edb`, `swd`, `places`, `competitor`)
  still validate and still appear in the editor and filter
- Blank source still stores as unset
- Unknown source strings still raise `ValidationError`
- Empty Catalog source filter still omits `source` from the query
- Source labels stay Title Case words (`Recommendation`, not
  `RECOMMENDATION`)

## Done when

- Import, create, and update accept `source=recommendation`
- Vetting notes with `source=recommendation` fill the column
- OpenAPI enums and generated admin types include `recommendation`
- Catalog filter and organization editor offer Recommendation
- `pytest tests/test_admin_imports.py tests/test_org_listing_status.py`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/organizations.spec.ts`

## Rollback

Revert the commit. No migration.

## Open questions

None.
