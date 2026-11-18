# Plan: free trial tick on per-class and monthly prices

**Status**: Approved
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
- `backend/src/app/services/enrichment/apply_rows.py` uses the same allowlist.
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
