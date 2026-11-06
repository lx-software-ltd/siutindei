# Plan: Let a reviewer finish an enrichment price

**Status**: Done
**Zone**: yellow

## Goal

A leaflet or website price can be applied when the model called it
`per_sessions` and left out the number of classes. The reviewer types
that number, and can also correct the pricing type, amount, and
currency, without rewriting the stored proposal. A pending price or
schedule says why apply would refuse it. A failed apply shows that
reason on the row.

A `per_sessions` row is not rewritten as `per_class`. Schedule rows
get the same activity and venue blockers as prices.

## Non-goals

- Guessing `sessions_count` from the quote.
- Rewriting or dismissing proposals already stored.
- Changing the `pricing_sessions_count_check` constraint.
- Schema or seed changes.

## Files

- `backend/src/app/services/enrichment/row_blockers.py`
- `backend/src/app/services/enrichment/extract.py`
- `backend/src/app/services/enrichment/sheet.py`
- `backend/src/app/services/enrichment/prompt.py`
- `backend/src/app/services/enrichment/apply_rows.py`
- `backend/src/app/services/enrichment/match.py`
- `backend/src/app/services/enrichment/store.py`
- `backend/src/app/api/admin_enrichment.py`
- `docs/api/admin.yaml`
- `docs/api/partner.yaml`
- `apps/admin_web` enrichment card, client types, tests, Playwright

## Invariants this change preserves

- A pending proposal's `proposed_value` is not rewritten on apply.
  Corrections stay in `overrides`.
- Apply still saves each proposal in its own savepoint.
- Older override keys (`area_id`, `category_id`, `age_min`, `age_max`,
  `location_id`) keep working.
- Nothing is written to the catalog before apply.

## Done when

- `pytest tests/test_enrichment_pricing_rows.py tests/test_org_enrichment_depth.py tests/test_org_enrichment.py tests/test_partner_org_enrichment.py`
- `pre-commit run ruff-format --all-files`
- Admin `npm run lint`, `npm run typecheck`, the enrichment vitest, and the organizations Playwright spec
- OpenAPI descriptions name the new override fields and `blockers`

## Rollback

Revert the branch. Stored proposals are unchanged. A reviewer goes
back to adding the price by hand.

## Open questions

None. A term price stays blocked until the reviewer supplies
`sessions_count` or changes the type. Schedule rows report missing
activity and venue the same way prices do.
