# Plan: Hong Kong neighbourhoods

**Status**: Done
**Zone**: red

## Goal

Add a `neighbourhood` level under all 18 Hong Kong districts. A location
in Hong Kong must point at a neighbourhood. The public wizard and the
location-fix sweep offer those neighbourhoods.

## Non-goals

- Neighbourhoods for Singapore or the UAE. Those districts stay leaves.
- Changing region UUIDs used by the home wizard.
- Replacing district pin boxes used by the location quality check.

## Files

- `backend/src/app/data/hk_neighbourhoods.py` — names, translations, centroids
- `backend/src/app/services/area_assignment.py` — nearest leaf for a pin
- `backend/db/alembic/versions/0045_hk_neighbourhoods.py`
- `backend/db/seed/seed_data.sql`
- `backend/src/app/api/admin_resource_location.py`
- `backend/src/app/api/admin_imports_lookups.py`
- `backend/src/app/api/admin_ticket_review.py`
- `backend/src/app/services/location_fix_prompt.py`
- `backend/src/app/services/location_fix_model.py`
- `backend/src/app/services/location_fix_registers.py`
- `docs/api/admin.yaml`, `docs/api/search.yaml`
- `docs/architecture/database-schema.md`
- `apps/admin_web` cascading area select and generated types
- `shared/home_wizard/home_wizard_choices.json` and its copies
- `apps/public_www` navigator, search params, search panel, results page
- `scripts/codegen/generate_activity_search_staging.py` and the fixture
- `apps/siutindei_app` home wizard

## Invariants this change preserves

- Search still matches an area and every descendant.
- Region UUIDs `a1111111-1111-1111-1111-111111111101` through `104` stay.
- A district with no children (Singapore, UAE, test fixtures) can still
  be a location's area.
- Hong Kong pin checks still resolve a neighbourhood up to its district.

## Done when

- `pytest tests/test_hk_neighbourhoods.py tests/test_alembic_revision_contract.py tests/test_admin_imports.py tests/test_location_fixes.py tests/test_location_fix_registers.py`
- `pytest tests/test_staging_search_store.py tests/test_home_wizard_choices.py`
- Admin web `npm run typecheck`
- Public site `npm test`
- Seed locations point at neighbourhoods. Existing Hong Kong locations
  are moved to the nearest neighbourhood in their district.

## Rollback

`alembic downgrade 0044_location_enrichment` moves locations back to
their district and deletes the neighbourhood rows.

## Open questions

None. Level name is `neighbourhood`. Depth is strict for Hong Kong.
All 18 districts are seeded. The wizard and the sweep expose them.
