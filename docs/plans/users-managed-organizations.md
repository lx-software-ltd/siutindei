# Plan: Managed organizations on the user accordion

**Status**: Accepted
**Zone**: yellow

## Goal

On the admin Users table, the expanded row shows a **Managed organizations**
field. Organizations whose `manager_id` is that user's Cognito sub are
listed as bullet points, ordered by name. When the user manages none, the
value is the same em dash (`—`) as the other empty fields in that panel.

The users list loads those organizations only when the Users screen asks
for them (`include=managed_organizations`). Manager pickers and other
callers of the same endpoint stay unchanged.

## Non-goals

- A new API Gateway route or a database index (`backend/infrastructure/**`
  and `backend/db/**` stay untouched).
- Changing who can be a manager, or how `manager_id` is assigned.
- Showing managed organizations in the table columns.
- Linking each organization name to the organization page.

## Files

- `docs/plans/users-managed-organizations.md`
- `docs/api/admin.yaml`
- `docs/architecture/lambdas.md`
- `backend/src/app/api/admin_cognito.py`
- `backend/src/app/api/admin_cognito_groups.py`
- `backend/src/app/db/repositories/organization.py`
- `tests/test_admin_cognito_list.py`
- `tests/test_repositories.py`
- `apps/admin_web/src/types/api-admin.generated.ts`
- `apps/admin_web/src/lib/api-client-cognito.ts`
- `apps/admin_web/src/components/admin/cognito-users-panel.tsx`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`
- `apps/admin_web/e2e/cognito-users.spec.ts`

## Invariants this change preserves

- One row expands in place. Role grant, revoke, and delete stay on
  Operations.
- Users still cannot modify their own account.
- `GET /v1/admin/cognito-users` without `include` does not query the
  database and does not add `managed_organizations`.
- Group membership is still resolved with one `list_users_in_group` call
  per managed group.

## Done when

- `pytest tests/test_admin_cognito_list.py tests/test_repositories.py`
  covers the include flag, the empty list, and name order.
- Playwright `e2e/cognito-users.spec.ts` expects the new label, bullet
  names, and the em dash.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- A browser pass expands a manager and a user with no organizations.

## Rollback

Revert the pull request.

## Open questions

None. No seed change: this reads `organizations.manager_id` and does not
change the schema.
