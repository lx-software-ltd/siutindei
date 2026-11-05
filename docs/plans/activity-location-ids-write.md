# Plan: Writable activity location_ids

**Status**: Done
**Zone**: yellow

## Goal

Let admin and partner activity create and update set `location_ids`
so a programme can attach to one or more venues of its organization.
Omit the field to leave existing joins. Send `[]` to unlink every
venue. Present, unknown, or other-organization ids are a `400`.

## Non-goals

- Schema or seed changes.
- Admin activities UI.
- New API Gateway paths.
- Inventing pricing or schedule rows so search lists a programme.
- Writing campus street addresses, phones, or emails into source.

## Files

- `backend/src/app/api/admin_resource_activity.py`
- `tests/test_activity_location_ids.py`
- `docs/api/admin.yaml`
- `docs/api/partner.yaml`
- `docs/architecture/data-quality.md`
- `apps/admin_web/src/types/api-admin.generated.ts`

## Invariants this change preserves

- An omitted `location_ids` leaves `activity_locations` unchanged.
- Joins still require locations of the same organization.
- Location-fix sweep still skips activities that already have a join.
- Partner GET still overlays `location_ids` from the join table.
- Org merge still unions joins only from source activities that had
  them.

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
