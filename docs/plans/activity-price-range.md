# Plan: Activity price ranges

**Status**: In review
**Zone**: red

`activity_pricing` lives in `backend/db`. This adds one nullable
column. Approved in chat: optional `amount_max`, no open-ended
"from" price, the outlier check stays on the lower bound, installed
apps may show that lower bound until they update, and the schema
and clients land together.

## Goal

A fee can be a range. `amount` stays the lower bound. `amount_max`
is the upper bound when the fee is a range, and null for a single
price. Search `price_min` and `price_max` match a range that overlaps
them. Sort, the per-class cap, and the class-price outlier check use
the lower bound.

## Non-goals

- An open-ended "from" price with no upper bound.
- A required pair of bounds, or renaming `amount`.
- A new price index.
- Rewriting stored enrichment proposals.

## Files

- `backend/db/alembic/versions/0069_pricing_amount_max.py`
- `backend/src/app/db/models/activity.py`
- `backend/src/app/db/repositories/pricing.py`
- `backend/src/app/db/search_conditions.py`
- `backend/src/app/api/schemas.py`
- `backend/src/app/api/search_page.py`
- `backend/src/app/api/admin_resource_pricing.py`
- `backend/src/app/api/admin_imports_allowed.py`
- `backend/src/app/api/admin_imports_export.py`
- `backend/src/app/services/catalog_version_shape.py`
- `backend/src/app/services/catalog_version_payload.py`
- `backend/src/app/services/staging_search_matching.py`
- `backend/src/app/services/staging_search_store.py`
- `backend/src/app/services/enrichment/` prompt, extract, sheet,
  blockers, apply, match, and the extraction version
- `docs/api/admin.yaml`, `docs/api/search.yaml`, `docs/api/partner.yaml`
- `docs/architecture/database-schema.md`, `decisions.md`,
  `data-quality.md`, `public-www.md`
- `docs/imports/admin-import-sample.json`
- `apps/admin_web` pricing panel, enrichment editor, generated types
- `apps/public_www` price formatting, mapping, and structured data
- `apps/siutindei_app` pricing model, entity, and mapper
- `tests/test_pricing_range.py`

## Invariants this change preserves

- A row with no `amount_max` matches, sorts, imports, and displays as
  it does today. `amount` remains the lower bound.
- `per_sessions` still requires `sessions_count`. `free` still stores
  amount 0 and has no upper bound.
- Import identity stays activity, venue, and pricing type. A file that
  omits `amount_max` is not a change against its baseline.
- A pending enrichment proposal is not rewritten. Corrections stay in
  overrides.
- The class-price outlier check still reads the lower bound.

## Done when

`alembic upgrade head` applies `0069_pricing_amount_max` and the seed
file still loads. `pytest tests/test_pricing_range.py` and
`pytest tests/test_alembic_revision_contract.py` pass, with the search,
import, and enrichment tests that read a price. Admin lint, typecheck,
and the pricing Playwright spec pass. Public website lint, typecheck,
and unit tests pass. `pre-commit run ruff-format --all-files` is clean.

## Rollback

Downgrade drops `pricing_amount_max_check` and `amount_max`. A ranged
row keeps its lower bound and loses the upper bound.

## Open questions

None.
