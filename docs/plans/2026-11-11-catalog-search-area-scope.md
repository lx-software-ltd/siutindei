# Plan: Catalog default follows SEARCH_AREA_SCOPE

**Status**: Done
**Zone**: red

Catalog itself is yellow (`apps/admin_web`). The stricter zone applies
because `.github/workflows/deploy-admin-web.yml` passes
`SEARCH_AREA_SCOPE` into the static build. That is one environment line.

## Goal

Stop hardcoding Stanley as the Catalog neighbourhood. Open Catalog on
the area named by the GitHub variable `SEARCH_AREA_SCOPE`, the same
value public search already uses.

## Non-goals

- Filtering Catalog when the variable names several areas that do not
  sit inside one region, district, or neighbourhood. The list API
  takes one `area_id`.
- Changing public search, seeds, or the organisation list query.
- Admin badges for organisations outside the public scope.

## Files

- `apps/admin_web/src/lib/catalog-defaults.ts` — resolve the variable
  against the geographic area tree.
- `apps/admin_web/next.config.js` — inline `SEARCH_AREA_SCOPE` as
  `NEXT_PUBLIC_SEARCH_AREA_SCOPE`.
- `.github/workflows/deploy-admin-web.yml` — pass the GitHub variable
  into the static build.
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
  — show the area name when the default is not a neighbourhood option.
- `apps/admin_web/src/components/admin/org-review/neighbourhood-filter.tsx`
  — show that name.
- Tests, the Playwright env, and the deployment notes.

## Invariants this change preserves

- Admins can still choose All neighbourhoods or any other leaf.
- An import-job deep link (`?job=`) still skips the default.
- Hong Kong neighbourhood ids stay the seeded values. No schema change.
- An empty variable opens Catalog on every neighbourhood.
- A region id is checked before a district slug, so `islands` is the
  Islands region.

## Done when

- `npx vitest run tests/lib/catalog-defaults.test.ts tests/components/admin/neighbourhood-filter.test.tsx` in `apps/admin_web`.
- `npm run lint` and `npm run typecheck` in `apps/admin_web`.
- Playwright opens Catalog on Stanley when `SEARCH_AREA_SCOPE` is
  `southern-stanley`, and an import-job link still omits `area_id`.

## Rollback

Revert the commits and redeploy admin web. No migration.

## Open questions

None. A scope of two disjoint areas leaves the filter on all
neighbourhoods, because one `area_id` cannot name that union.
