# Plan: free trial tick on per-class and monthly prices

**Status**: Approved, with a follow-up for the review notes
**Zone**: yellow, plus an approved seed edit under `backend/db/seed/`

## Goal

An admin can tick "Free trial class offered" on a `per_class`, `per_sessions`, or `per_month` price, by form or by import, and the tick is stored. The seeded per-class price carries the tick so a local database shows it.

## Non-goals

- Allowing the tick on `per_hour`, `per_day`, `per_year`, or `free`.
- Making website enrichment propose a free trial. Apply still drops the tick on a type that cannot store it.
- A database migration, a backfill, or a change to rows already saved.
- Any change to the public website, the Flutter app, or the search API. They already read the column as stored.

## Files

- `tests/test_pricing_free_trial.py` covers create, update, and enrichment apply.
- `tests/test_admin_imports.py` covers a per-class import and a second import of the same row.
- `backend/src/app/db/models/enums.py` holds the allowlist.
- `backend/src/app/api/admin_resource_pricing.py` stores the tick for the allowlist. `sessions_count` stays tied to `per_sessions`.
- `backend/src/app/services/enrichment/row_blockers.py` `pricing_fields` uses the same allowlist. Apply passes that value through.
- `apps/admin_web/src/components/shared/pricing/pricing-types.ts` and `pricing-panel.tsx` show and send the tick for the allowlist.
- `apps/admin_web/e2e/pricing.spec.ts` ticks the box on a monthly price and checks the request.
- `docs/api/admin.yaml` states the rule. `docs/architecture/database-schema.md` notes that the database does not enforce it.
- `backend/db/seed/seed_data.sql` sets the existing per-class row to `true`.

## Invariants this change preserves

- `sessions_count` is required for `per_sessions` and cleared for every other type.
- Types outside the allowlist still have the tick forced to `false`, with no new error response.
- No route, response shape, or column changes.

## Done when

- `pytest tests/test_pricing_free_trial.py tests/test_pricing_month_year.py tests/test_admin_imports.py tests/test_search_public_details.py` passes.
- `pre-commit run ruff-format --all-files` is clean.
- In `apps/admin_web`: `npm run lint`, `npm run typecheck`, and Playwright `pricing.spec.ts` pass.
- The pricing screen shows the tick on Per class and Monthly, hides it on Hourly, and a saved Per class row still shows the tick.

## Rollback

Revert the change. Rows ticked in the meantime keep `true` until the next save of a type the old handlers clear.

## Decisions

- The allowlist is `per_class`, `per_sessions`, and `per_month`.
- No backfill of prices imported before this change.
- The existing per-class seed row stores the tick. No new seed row.
- The staging search fixture stays as it is.

## Follow-up

The public site already reads the stored tick, so it stays unchanged.

- A skipped import (`allow_updates` false) leaves the baseline where it was. A later import that allows updates can still apply that file, including a free-trial tick the first pass skipped. An unchanged row still refreshes its baseline.
- An import of a type outside the allowlist compares the tick as `false`, so a second import of the same hourly row is `unchanged`.
- `docs/api/admin.yaml` `FreeTrialPricingType` is the allowlist. Python tests that it matches `FREE_TRIAL_PRICING_TYPES`. The admin form's set must satisfy that generated union.
- Website enrichment proposes `free_trial_class_offered: true` only when the quote offers a trial and the type is on the allowlist. A reviewer can tick or clear it. A proposal that omits the field leaves a stored tick as it is.
- Re-running `backend/db/seed/seed_data.sql` sets the sample per-class row to `true`. No other price is updated.
- The enrichment test asserts stored rows, not the allowlist constant against itself.
