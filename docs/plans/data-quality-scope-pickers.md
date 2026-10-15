# Plan: Data quality scope pickers

**Status**: Done
**Zone**: yellow

## Goal

On Data quality · Runs, choosing one organization opens an
Organization field. Typing a name uses the existing organization
autocomplete (`searchUserOrganizations`, the same search the
feedback form uses) and the run stores the selected organization id.

Choosing one import opens a dropdown of the latest 20 import jobs.
Each option shows that job's create time. The run still sends the
job id.

## Non-goals

- A new search or import-list API
- Changing how a run resolves `org_id` or `import_job_id`
- Showing import ids in the dropdown

## Files

- `apps/admin_web/src/components/ui/organization-autocomplete.tsx`
- `apps/admin_web/src/components/admin/feedback-form.tsx`
- `apps/admin_web/src/components/admin/data-quality/runs-panel.tsx`
- `apps/admin_web/src/lib/api-client-org-review.ts`
- Unit tests for the autocomplete and the runs panel
- `apps/admin_web/e2e/data-quality.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`

## Invariants this change preserves

- Pending review and All scopes still start a run with no extra id.
- A run still posts `org_id` or `import_job_id`, not a display name
  or a timestamp.
- Feedback still searches organizations by name and submits the
  selected id.
- Import history still lists jobs without a forced page size.

## Done when

- Unit tests cover name suggestions and the 20-import dropdown.
- Playwright selects an organization by name and an import by its
  create time, and the posted scope carries the ids.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.

## Rollback

Revert the commit. No schema or seed change.

## Open questions

None. Option labels use `formatDateTime`, the same create-time
text as other admin tables. The option value stays the job id.
