# Plan: listings stop at age 18

**Status**: In review
**Zone**: yellow, plus one red slice

The red slice is `backend/db/alembic/versions/0068_listing_age_cap.py`.
The owner asked for the database check after the review named it.

## Goal

A stored listing age is at most 18. A higher age is saved as 18.
`age_min` may equal `age_max`. It cannot be higher than `age_max`
after that cap, and it cannot be negative.

Create, update, import, and enrichment all use `cap_listing_ages`.
The admin form caps the same way. The database rejects a row that
bypasses those writes.

## Non-goals

Search filters still accept an older wanted age. No change to the
three live rows already set to 18.

## Files

- `backend/src/app/db/age_bounds.py`
- `backend/src/app/api/admin_resource_activity.py`
- `backend/src/app/api/admin_imports_fields.py`
- `backend/src/app/services/enrichment/apply_rows.py`
- `backend/src/app/services/enrichment/prompt.py`
- `backend/src/app/services/org_review.py`
- `backend/src/app/services/org_review_sql.py`
- `backend/src/app/db/models/activity.py`
- `backend/db/alembic/versions/0068_listing_age_cap.py`
- `docs/api/admin.yaml`
- `docs/architecture/database-schema.md`
- `apps/admin_web/src/lib/listing-age.ts`
- `apps/admin_web/src/components/shared/activities-panel.tsx`
- `apps/admin_web/src/components/admin/organization-enrichment-proposals.tsx`

## Invariants this change preserves

`age_min` stays at least 0. A missing age on a flat import still
defaults to 0–18, using the same ceiling constant. Search `age_max`
is a filter, not a stored listing age. A place or a meal at 0–18 is
a real "all children" range, so the import-default warning stays on
classes, camps, and nurseries.

## Done when

`pytest` covers the cap, a single age, import, enrichment, the age
check, and the review warning. `alembic upgrade head` applies
`0068_listing_age_cap`. Admin lint, typecheck, and the age end-to-end
specs pass. `npm run generate:api` leaves no further diff.

## Rollback

Revert the commit and run `alembic downgrade -1` for this revision.
Rows already stored at 18 stay at 18.

## Open questions

None.
