# Plan: Fix the 5–10 Nov CloudWatch failures

**Status**: Done
**Zone**: yellow

## Goal

Stop the enrichment crawler from crashing the out-of-VPC proxy on
page URLs that contain a space or a non-ASCII character. Treat an
existing activity schedule as already applied instead of raising a
unique-constraint error. Read a non-JSON API-key rotation secret as
“no previous key”. Surface a refused enrichment image as a validation
error instead of an unhandled exception.

## Non-goals

- Redriving `lxsoftware-siutindei-category-suggestion-dlq`. The dismiss
  fix is already deployed. This role cannot decrypt the queue or call
  `sqs:StartMessageMoveTask`.
- Rotating or deleting the live mobile API key. Redriving that Lambda
  dead-letter message would rotate the production key.
- Allowing image responses that are HTTP 403 or not jpeg, png, webp,
  or gif.
- Evolvesprouts Eventbrite, the lxsoftware admin Lambda dead-letter
  queue, API Gateway execution logging, and the admin authorizer’s
  `COGNITO_USER_POOL_ID`. Those are outside this repo or in the red
  zone.
- A schema or seed change.

## Files

- `docs/plans/cloudwatch-nov-2026-fixes.md`
- `backend/src/app/services/enrichment/fetch.py`
- `backend/src/app/services/enrichment/apply_rows.py`
- `backend/src/app/services/enrichment/apply_media.py`
- `backend/lambda/api_key_rotation/handler.py`
- `tests/test_org_enrichment.py`
- `tests/test_api_key_rotation.py`

## Invariants this change preserves

- A crawl still refuses private hosts, credentials, and non-http URLs
  before it connects.
- An existing schedule’s rows are not rewritten or duplicated.
- `zh-HK` is still stored as `yue`.
- A refused image is still not attached to the organization.
- A JSON API-key secret with `api_key_id` is still used to retire the
  previous key. The secret value is not logged.

## Done when

- `pytest tests/test_org_enrichment.py tests/test_api_key_rotation.py`
- `pre-commit run ruff-format --all-files`

## Rollback

Revert the commit. No migration.

## Open questions

None.
