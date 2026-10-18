# Plan: Enrichment region and a typed website

**Status**: Done
**Zone**: yellow

## Goal

The location proposal selects the region (and the district, when known)
so an admin does not start the area picker from a blank region. Enrich
from website enables as soon as the Website field has a URL, and that
URL is the crawl seed. Saving the organization is not required.

## Non-goals

- Saving the typed website onto the organization.
- Letting a region or district be stored as the location's area. A
  location still needs a neighbourhood before apply.
- A migration or a seed change.

## Files

- `backend/src/app/services/enrichment/places.py`
- `backend/src/app/services/enrichment/refine.py`
- `backend/src/app/services/enrichment/prompt.py`
- `backend/src/app/services/enrichment/sheet.py`
- `backend/src/app/services/enrichment/extract.py`
- `backend/src/app/services/enrichment/store.py`
- `backend/src/app/api/admin_enrichment.py`
- `docs/api/admin.yaml`
- Admin enrichment button, proposal area select, their tests, and the
  organizations Playwright spec
- `tests/test_enrichment_place.py`
- `tests/test_org_enrichment.py`

## Invariants this change preserves

- Apply still rejects a location whose area is not a neighbourhood.
- A typed website is validated with the same seed checks and is not
  written onto the organization.
- An empty Website field does not start a run.
- Place and logo lookups stay inside the existing time budget.
- One apply can set one logo.

## Done when

- `pytest tests/test_enrichment_place.py tests/test_org_enrichment.py`
- `pre-commit run ruff-format --all-files`
- `npm run lint`, `npm run typecheck`, and the enrichment vitest in
  `apps/admin_web`
- Playwright covers a preselected region and a typed, unsaved website
- `python3 scripts/check_openapi_routes.py`

## Rollback

Revert the branch. A run already queued keeps its seed URL. No
migration.

## Open questions

None.
