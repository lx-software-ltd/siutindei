# Plan: Manual catalog source

**Status**: Done
**Zone**: yellow (API and admin UI). Data backfill and seed
touch `backend/db/**` (red) because unset source is stored as
NULL today.

## Goal

Rename the catalog source that the admin editor labeled **None**
(stored unset) to **Manual**. Import, create, update, and the
Catalog source filter accept `source=manual`. Existing empty
rows count as Manual.

## Non-goals

- A database CHECK on `organizations.source` (the column stays
  free text; allowed values stay in the API)
- Relabeling LCSD, EDB, and the other catalog tokens in the
  Source column
- Changing description origin, which still offers None

## Files

- `docs/plans/manual-source-type.md`
- `backend/src/app/api/admin_imports_catalog.py`
- `backend/src/app/api/admin_org_review.py`
- `backend/src/app/api/admin_list_filters.py`
- `backend/src/app/services/org_review.py`
- `backend/src/app/services/org_review_sql.py`
- `backend/db/alembic/versions/0059_manual_org_source.py`
- `backend/db/seed/seed_data.sql`
- `docs/api/admin.yaml`
- `docs/architecture/database-schema.md`
- `apps/admin_web/src/components/shared/organizations/organization-form-utils.tsx`
- `apps/admin_web/src/components/shared/organizations-panel.tsx`
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
- `apps/admin_web/src/types/api-admin.generated.ts`
- `tests/test_admin_imports.py`
- `tests/test_org_listing_status.py`
- `tests/test_admin_list_filters.py`
- `tests/test_org_review.py`
- `tests/test_manual_org_source_backfill.py`
- `apps/admin_web/tests/components/shared/organization-source-options.test.ts`
- `apps/admin_web/e2e/organizations.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`

## Invariants this change preserves

- Existing sources (`lcsd`, `edb`, `swd`, `places`,
  `competitor`, `recommendation`) still validate and still
  appear in the editor and filter
- Blank source on import still stores as unset, and the Manual
  filter still includes those rows
- Unknown source strings still raise `ValidationError`
- Empty Catalog source filter still omits `source` from the query
- Description origin still offers None
- Source labels stay Title Case words (`Manual`, not `MANUAL`)

## Done when

- Import, create, and update accept `source=manual`
- Vetting notes with `source=manual` fill the column
- OpenAPI enums and generated admin types include `manual`
- Catalog filter and organization editor offer Manual and no
  longer offer None for catalog source
- Unset sources display as Manual
- `pytest tests/test_admin_imports.py tests/test_org_listing_status.py tests/test_admin_list_filters.py tests/test_org_review.py tests/test_manual_org_source_backfill.py tests/test_alembic_revision_contract.py`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/organizations.spec.ts`

## Rollback

Revert the commit. `downgrade` leaves stored `manual` values in
place. Reverting the code does not invent a None source.

## Open questions

None.
