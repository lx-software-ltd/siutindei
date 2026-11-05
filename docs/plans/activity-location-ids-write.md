# Plan: Writable activity location_ids

**Status**: In review
**Zone**: yellow

## Goal

Let admin, manager, and partner activity create and update set
`location_ids` so a programme can attach to one or more venues of
its organization. Omit the field to leave existing joins. Send `[]`
to unlink every venue that has no pricing or schedule for that
activity. Present, unknown, or other-organization ids are a `400`.
The response lists ids in location-id order. Sending the current
list again does not rewrite joins. A later import does not put a
removed venue back on an existing activity.

## Non-goals

- Schema or seed changes.
- Admin activities UI.
- New API Gateway paths.
- Inventing pricing or schedule rows so search lists a programme.
- Writing campus street addresses, phones, or emails into source.

## Files

- `backend/src/app/api/admin_resource_activity.py`
- `backend/src/app/api/admin_crud.py`
- `backend/src/app/api/admin_imports_upsert.py`
- `backend/src/app/api/partner_category_reviews.py`
- `backend/src/app/db/repositories/activity.py`
- `backend/src/app/services/org_review.py`
- `tests/test_activity_location_ids.py`
- `tests/test_admin_imports.py`
- `docs/api/admin.yaml`
- `docs/api/partner.yaml`
- `docs/architecture/data-quality.md`
- `apps/admin_web/src/types/api-admin.generated.ts`

## Invariants this change preserves

- An omitted `location_ids` leaves `activity_locations` unchanged.
- An unchanged list does not delete or insert join rows.
- Joins still require locations of the same organization.
- A venue that still has pricing or a schedule for the activity
  cannot be removed.
- Location-fix sweep still skips activities that already have a join.
- Partner GET returns the same `location_ids` the activity serializer
  writes. It does not query the join table a second time.
- A catalog import links a venue only when it creates the activity.
- Org merge still unions joins only from source activities that had
  them.
- Managers and organization-scoped keys can set venues only for their
  own organization.

## Done when

`pytest tests/test_activity_location_ids.py` passes.
`python3 scripts/check_openapi_routes.py` passes.
`pre-commit run ruff-format --all-files` is clean.

After deploy, partner PUT can attach International Montessori School
programmes to the campus venues already on the survivor organization.

## Rollback

Revert this pull request. Existing reads of `location_ids` stay.

## Open questions

None. Production writes wait for this API to deploy.
