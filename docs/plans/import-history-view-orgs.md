# Plan: Catalog from import history View orgs

**Status**: Implemented
**Zone**: yellow

## Goal

Imports · History **View orgs** opens Catalog filtered to every organization that import created or updated.

## Non-goals

- Changing which job is stored on `organizations.import_job_id`. A later import still leaves the creating job there.
- Showing unchanged, skipped, or failed organizations.
- A new API route. The existing `import_job_id` query on `GET /v1/admin/org-review` grows the match.

## Files

- `docs/plans/import-history-view-orgs.md`
- `backend/src/app/api/admin_org_review.py`
- `backend/src/app/api/admin_org_review_import.py`
- `tests/test_org_review.py`
- `docs/api/admin.yaml`
- `docs/architecture/decisions.md`
- `apps/admin_web/src/components/admin/org-review/import-history-panel.tsx`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`
- `apps/admin_web/e2e/org-review.spec.ts`

## Invariants this change preserves

- `organizations.import_job_id` stays the job that created the row.
- Catalog without `?job=` still lists every organization.
- An organization result of `unchanged`, `skipped`, or `failed` does not add that organization.
- A child catalog version alone does not add the organization. A child write that bumped the organization version does, because that version is `updated` for this job.
- Show all still clears `?job=`.

## Done when

- `pytest tests/test_org_review.py::test_review_list_includes_orgs_created_or_updated_by_import`
- `python3 scripts/check_python_file_length.py`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/org-review.spec.ts` in `apps/admin_web`

## Rollback

Revert the branch. No schema change.

## Open questions

None. Created and updated means the creating `import_job_id`, an organization catalog version with action `created` or `updated` for that job, or a stored organization result with status `created` or `updated`.
