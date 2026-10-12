# Plan: Organization website

**Status**: Done
**Zone**: red

## Goal

Store an optional website on every organization. Catalog imports write
that field. A one-off backfill copies websites out of import files
that already ran and removes the "website is accepted but not stored"
warning from those jobs.

## Non-goals

- Requiring a website, or copying `source_url` into `website`.
- Public search and the mobile app.
- Changing skip-mode imports. A later import with updates off still
  leaves the existing organization unchanged.

## Files

- `backend/db/alembic/versions/0047_org_website.py`
- `backend/src/app/db/models/organization.py`
- Organization create, update, serialize, export, review bulk fields,
  merge fill, and duplicate host matching.
- `backend/src/app/api/admin_imports_upsert.py` and
  `admin_imports_fields.py`
- `backend/src/app/services/import_website_backfill.py` and
  `scripts/ops/backfill_org_websites.py`
- `docs/api/admin.yaml`, generated admin types, and the organization
  form.
- `docs/architecture/database-schema.md` and
  `docs/architecture/data-quality.md`

## Invariants this change preserves

- `source_url` stays the catalog page. Managers still cannot write it.
- `website` is optional, at most 400 characters, and managers can set it.
- Omitting `website` on an update leaves the stored value in place.
- Skip mode does not write `website` on a future import.
- Duplicate matching still scores the catalog page host. It also
  scores the organization website host in the same bucket.
- A merged-away organization fills the survivor's website only while
  that website is empty. A deleted organization is not recreated.

## Done when

- `pytest tests/test_alembic_revision_contract.py tests/test_admin_imports.py tests/test_org_review.py tests/test_import_website_backfill.py tests/test_org_duplicates.py tests/test_org_listing_status.py`
- `python3 scripts/check_openapi_routes.py`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/organizations.spec.ts e2e/manager-dashboard.spec.ts` in `apps/admin_web`
- `pre-commit run ruff-format --all-files` before the Python commit

## Rollback

Revert the branch and drop `organizations.website`. Values stored only
in that column go with it. `source_url` stays. Restoring the discarded
warning text needs the previous job JSON.

## Backfill rules

The script reads `ADMIN_IMPORT_EXPORT_BUCKET` and only completed jobs
that still carry the discard warning. Import files expire after 7 days,
so older jobs often have nothing to read.

- A missing file keeps the warning, and that organization's website
  stays empty.
- A readable file stores the website, then the warning is removed.
- Jobs run by completion time, so a retry replaces an earlier pass in
  the same run.
- A website already stored, including one typed after deploy, is left
  in place. A later file in the same run may replace a website this
  run wrote.
- A skipped row fills `website` only while it is empty.
- Dry runs remove the warning only when the file is still readable.
- Failed and running jobs are left alone.
