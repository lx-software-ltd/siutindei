# Plan: Add a manager by email

**Status**: Accepted
**Zone**: red

## Goal

On the admin organization Manager field, typing a full email that matches
no Cognito user offers **Add that email as manager**. Choosing it creates
a passwordless account, puts the account in the `manager` group, and
selects that user. Saving the organization still sends the Cognito `sub`.

## Non-goals

- Granting the `manager` group when an existing user is picked from the list.
- Sending an invitation email. Sign-in stays the existing one-time code.
- Changing manager self-service. That screen keeps a read-only email.
- Letting catalog importers create accounts.

## Files

- `docs/plans/add-manager-by-email.md`
- `docs/api/admin.yaml`
- `docs/architecture/lambdas.md`
- `docs/architecture/aws-assets-map.md`
- `backend/infrastructure/lib/api-stack.ts`
- `backend/src/app/api/admin.py`
- `backend/src/app/api/admin_cognito.py`
- `backend/src/app/api/admin_cognito_manager.py`
- `tests/test_admin_cognito_manager_create.py`
- `apps/admin_web/src/lib/api-client-cognito.ts`
- `apps/admin_web/src/lib/api-client.ts`
- `apps/admin_web/src/types/api-admin.generated.ts`
- `apps/admin_web/src/components/shared/organizations/manager-combobox.tsx`
- `apps/admin_web/tests/components/shared/manager-combobox.test.tsx`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`
- `apps/admin_web/e2e/organizations.spec.ts`

## Invariants this change preserves

- `manager_id` remains a Cognito sub.
- `POST /v1/admin/cognito-users` is admin-only.
- The confirmation secret is random, never returned, and never logged.
- Confirmed accounts keep their existing password.
- Repeating the same email returns the existing user and ensures the
  `manager` group.

## Done when

- `pytest tests/test_admin_cognito_manager_create.py`
- `python3 scripts/check_openapi_routes.py`
- `node scripts/check-lambda-docs.mjs`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Vitest `manager-combobox.test.tsx`
- Playwright organization spec for the add action
- `npm run lint` and `npm run build` in `backend/infrastructure`
- `pre-commit run ruff-format --all-files` before the Python commit

## Rollback

Remove the POST method, the handler branch, and the combobox action.
Accounts already created stay ordinary Cognito users.

## Open questions

None. Create-on-click, grant the manager group, and send no invitation
email were accepted with the implementation request.
