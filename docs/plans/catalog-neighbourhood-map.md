# Plan: Catalog neighbourhood filter and map

**Status**: Done
**Zone**: yellow

## Goal

Let Catalog filter organizations by neighbourhood, then show every
matching location on a Google Map. The map uses
`NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`, the same variable as the public
website.

## Non-goals

- A new geographic level or a seed change. Neighbourhood rows already
  exist under the 18 Hong Kong districts.
- A new API Gateway route. `area_id` and `include` are query parameters
  on `GET /v1/admin/org-review`.
- A new Google Cloud key. Catalog reuses the public website key.
  The admin deploy workflow now passes that same variable. The key's
  allowed websites still have to include the admin host.

## Files

- `backend/src/app/api/admin_org_review.py` filters by area and returns
  `map_locations` when `include=locations`.
- `docs/api/admin.yaml` and the generated admin types.
- `apps/admin_web` Catalog filter, Table | Map switch, and map.
- `tests/test_org_review.py`.
- `apps/admin_web/e2e/organizations.spec.ts` and the org-review mock.

## Invariants this change preserves

- The review list stays ordered and paginated. Other filters still
  apply.
- An organization matches when any location sits in the selected area
  or a descendant.
- Hong Kong locations stay on neighbourhood leaves. A district with no
  children can still be chosen.
- Detail responses keep full location records. Pins are
  `map_locations` on the list only.
- The table request does not ask for pins.

## Done when

- `pytest tests/test_org_review.py`
- `pre-commit run ruff-format --all-files`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Playwright covers the neighbourhood combobox and the map links
- No seed change

## Rollback

Revert the commit. No migration.

## Open questions

None. The map key is `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`.
