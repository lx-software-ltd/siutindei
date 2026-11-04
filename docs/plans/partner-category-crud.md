# Plan: Partner activity category CRUD

**Status**: Done
**Zone**: yellow

## Goal

Let a full-access `crud` partner key create and update activity
categories, using the same validation as the admin routes. Reading
already exists: a full-access key, including `read` scope, can
`GET /v1/partner/activity-categories` and
`GET /v1/partner/activity-categories/{id}`. Signed-in users can
`GET /v1/user/activity-categories`. Delete of an empty leftover
category already exists for a full-access `crud` key.

## Non-goals

- A new API Gateway resource. The routes ride `/v1/partner/{proxy+}`.
- Letting an organization-scoped key read or write the catalog.
- Admin-web UI. The admin console already edits categories.
- Schema or seed changes.

## Files

- `backend/src/app/api/partner_activity_categories.py`
- `tests/test_partner_activity_categories.py`
- `docs/api/partner.yaml`
- `docs/architecture/lambdas.md`
- `docs/architecture/security.md`
- `docs/architecture/category-suggestions.md`
- `docs/architecture/aws-assets-map.md`

## Invariants this change preserves

- Admin category CRUD.
- Full-access `read` keys can still list and fetch a category, and
  still cannot write.
- Organization-scoped keys still receive `403`.
- Delete still refuses Pending categorisation, wizard categories,
  categories with children, and categories assigned to an activity.
- The same name under one parent is still rejected.

## Done when

`pytest tests/test_partner_activity_categories.py` passes.
`python3 scripts/check_openapi_routes.py` and
`node scripts/check-lambda-docs.mjs` pass.

## Rollback

Revert this pull request. List, detail, and delete keep working.
