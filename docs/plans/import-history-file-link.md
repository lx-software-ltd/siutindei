# Plan: Link import history files to S3

**Status**: Done
**Zone**: yellow

## Goal

In Import history, the file value on each row opens that import's
JSON object in S3 when the object is still in the bucket. The list
response includes a presigned GET. The admin table and the expanded
row use that URL. Clicking the file does not expand the row.

## Non-goals

- A new API Gateway route. `backend/infrastructure/**` stays untouched.
- Changing the 7-day import object lifecycle.
- Putting the URL on the import process response or on
  `GET /v1/admin/imports/{job_id}`.

## Files

- `backend/src/app/api/admin_imports_objects.py` signs each listed object key.
- `backend/src/app/api/admin_imports.py` returns that URL on the history list.
- `docs/api/admin.yaml` and the generated admin types.
- `docs/architecture/lambdas.md` notes the presigned history URL.
- `apps/admin_web` history panel, list hook, client type, fixture, and Playwright spec.
- `tests/test_import_job_lifecycle.py`.

## Invariants this change preserves

- History stays admin-only. Importers still cannot list jobs.
- Only keys under `admin/imports/` are signed. A foreign key is listed
  without a URL.
- Jobs older than 7 days have no URL. The bucket lifecycle already
  deletes those objects.
- A signing failure leaves the list readable without `download_url`.
- Export downloads keep the same presign helper and 900-second
  attachment expiry.
- The stored `object_key` text stays the link label. Retry still sends
  that key.

## Done when

- `pytest tests/test_import_job_lifecycle.py`
- `python3 scripts/check_python_file_length.py`
- `python3 scripts/check_openapi_routes.py`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/org-review.spec.ts` in `apps/admin_web`
- `pre-commit run ruff-format --all-files` before the Python commit

## Rollback

Revert the branch. No schema change.

## Open questions

None. History links are inline, last one hour, and the list refreshes
every 30 minutes. The download filename drops the 32-character key
prefix.
