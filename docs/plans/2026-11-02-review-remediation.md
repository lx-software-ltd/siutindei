# Plan: Review remediation (public speed, admin reuse, backend hot path)

**Status**: Approved (implement the 2026-11-02 review)
**Zone**: yellow (touches `backend/src`, `apps/admin_web/src`, `docs/api`; red paths are the CloudFront function, deploy script, and the schedule-entry index migration, included because the review plan named them)

## Goal

Implement the review workstreams: public-site critical path and code reduction, admin client and panel reuse, and the backend search hot path, route table, bundle split, query plan, PostgreSQL-only tests, ruff ratchet, and fixture single-source.

## Non-goals

- Flutter app.
- Changing the public search sort order (day, start minute, schedule id).
- Adopting `openapi-fetch` at call sites. Keep generated types; remove the unused client.

## Files

- `apps/public_www/**` for workstreams A and B.
- `backend/src/app/api/search.py`, `search_validation.py`, `db/queries.py`, `db/engine.py`, `api/schemas.py`, `services/staging_search_store.py`.
- `backend/src/app/api/admin.py` route table.
- `backend/scripts/build_lambda_bundle.py` and `requirements-core.txt` / `requirements-admin.txt`.
- `docs/api/search.yaml`, `docs/architecture/lambdas.md`.
- `apps/admin_web/src/**` for workstream C.
- `backend/infrastructure/lib/public-www-stack.ts` and `scripts/deploy/deploy-public-www.sh` for the edge redirect and cache headers.
- `backend/db/alembic/versions/0058_entry_order_idx.py` for the schedule-entry index. Seed data is unchanged (index only).

## Invariants this change preserves

- Public search default response shape stays `view=full` so the Flutter app is unchanged.
- Admin and manager HTTP paths stay the same.
- Existing proposal routes stay as aliases.
- Production search stays on Aurora (`STAGING_SEARCH_DATA_ENABLED=false`).
- No secrets, PII, or `Cors.ALL_ORIGINS`.

## Done when

Public www lint, typecheck, and vitest pass. Admin lint and typecheck pass. Backend pytest against PostgreSQL passes. `ruff check` is clean under the widened rule set.

## Rollback

Revert the branch. The new Alembic revision only adds an index; downgrade drops it.

## Open questions

None. The review plan is the spec.
