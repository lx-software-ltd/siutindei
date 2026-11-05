# Plan: Monthly and yearly prices

**Status**: In review
**Zone**: red

The pricing enum lives in `backend/db`. This adds values. It does
not change existing rows.

## Goal

Add `per_month` and `per_year` to `pricing_type`. A monthly school
fee and a yearly charge, such as the IMS Annual Capital Levy, can
each be a price on the same activity and venue.

## Non-goals

- A label field that distinguishes two monthly tiers.
- Weekly schedules.
- Seed rows for a real school.
- Schema changes beyond the enum values.

## Files

- `backend/db/alembic/versions/0060_pricing_month_year.py`
- `backend/src/app/db/models/enums.py`
- `docs/api/admin.yaml`
- `docs/api/partner.yaml`
- `docs/api/search.yaml`
- `docs/architecture/database-schema.md`
- `docs/architecture/decisions.md`
- `apps/admin_web/src/components/shared/pricing/pricing-types.ts`
- `apps/public_www/src/lib/activities/listing-utils.ts`
- `apps/siutindei_app/lib/domain/entities/activity.dart`
- `apps/siutindei_app/lib/config/constants.dart`
- `apps/siutindei_app/lib/features/search/widgets/activity_card.dart`
- `tests/test_pricing_month_year.py`

## Invariants this change preserves

- Existing prices stay `per_class`, `per_sessions`, `per_hour`,
  `per_day`, or `free`.
- `per_sessions` still requires `sessions_count`.
- `free` still stores amount 0.
- Seed SQL still inserts `per_class` and does not use the new values.

## Done when

`alembic upgrade head` applies `0060_pricing_month_year`.
`pytest tests/test_pricing_month_year.py` and
`pytest tests/test_alembic_revision_contract.py` pass.

Production IMS prices wait until this enum is deployed. Tuition is
`per_month`. The Annual Capital Levy is `per_year` on Casa and
Elementary only.

## Rollback

Downgrade deletes `per_month` and `per_year` rows, then restores the
previous enum.

## Open questions

None. Two monthly options at one venue are two `per_month` rows.
The catalog has no tier name.
