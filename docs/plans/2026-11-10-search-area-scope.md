# Plan: Limit public search to selected Hong Kong areas

**Status**: Implemented
**Zone**: red (infrastructure and deploy workflows), yellow (search API), green (public website)

## Goal

A GitHub variable `SEARCH_AREA_SCOPE` limits public search to selected
Hong Kong regions, districts, or neighbourhoods. Unset shows everything.

## Non-goals

- Mobile area-chip changes. The API field `area_scope` is in place for that.
- Admin catalog badges for organisations outside the public scope.
- Changing which neighbourhood a location is stored on.

## Files

- Search query, handler, staging fixture store, and OpenAPI.
- CDK parameter `SearchAreaScope`, production params, deploy and promote workflows.
- Public website search panel, home wizard, staging filter, and deep-link notice.

## Invariants this change preserves

- An empty variable matches today's search results.
- Partner search is not filtered.
- A direct `activity_id` lookup still returns that activity.
- Locations stay on neighbourhood leaves. No schema change.

## Done when

`pytest tests/test_search_area_scope.py tests/test_search_category_filter.py tests/test_search_handler.py`
and `npm test` plus `npm run lint` in `apps/public_www`.

## Rollback

Unset `SEARCH_AREA_SCOPE` and deploy the backend and the public website.
The parameter is passed when empty, so the previous list does not stick.

## Open questions

None. Regions with nothing selected are disabled. Neighbourhoods outside
the list are hidden. Direct activity links stay open. Partner search is
exempt. Mobile controls wait for a later change.
