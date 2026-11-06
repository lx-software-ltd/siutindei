# Plan: API latency alarm and cold-start fixes

**Status**: Approved
**Zone**: red

The user asked to implement the latency follow-up. `backend/infrastructure/**`
and `backend/src/app/auth/**` are red; the Cognito list change is yellow.
Approval is the request to implement the changes.

## Goal

Stop the volume-gated API latency alarm paging on prep traffic, and shorten
the two cold paths that produce the 3–13 s requests: the partner API-key
authorizer and `SiutindeiAdminFunction`.

## Non-goals

- Draining the stale category-suggestion and API-key-rotation DLQ messages.
- Replacing the account-level API Gateway CloudWatch role. The live role
  belongs to another stack, and both APIs stopped logging when it changed.
- Raising provisioned concurrency above two. The site is not live; the
  traffic is one partner-key client plus the admin console.

## Files

- `backend/infrastructure/lib/constructs/ops-alarms.ts`
- `backend/infrastructure/lib/api-stack.ts`
- `backend/infrastructure/scripts/assert-existing-db.ts`
- `backend/src/app/api/__init__.py`
- `backend/src/app/auth/__init__.py`
- `backend/src/app/auth/api_key_authorizer.py`
- `backend/src/app/api/admin_cognito.py`
- `backend/src/app/api/admin_cognito_groups.py`
- `tests/test_admin_cognito_list.py`
- `tests/test_api_key_authorizer_imports.py`
- Architecture docs that describe the alarm, the authorizer, and the stack size.

## Invariants this change preserves

- A revoked partner key stops working. The bound is 15 minutes, not 5.
- `GET /v1/admin/cognito-users` still returns `groups` on every user.
- Category-suggestion SQS keeps invoking the admin function's `$LATEST`,
  so a long OpenRouter job does not sit on a warm HTTP environment.
- The ops alarm logical IDs stay put. Only the latency metric changes.
- The main stack stays at or under 500 CloudFormation resources.

## Done when

- `npm run build` and `npm run test:infra` in `backend/infrastructure`.
- `pytest tests/test_admin_cognito_list.py tests/test_api_key_authorizer_imports.py`.
- `pre-commit run ruff-format --all-files` before the Python commit.

## Rollback

Revert the commit. The alarm name change replaces that one alarm on the
next deploy. Provisioned concurrency stops billing when the alias is gone.

## Open questions

None. Fifteen minutes of key-revocation lag is the short end of the range
discussed, and two warm environments is the low end because this traffic
is pre-launch prep.
