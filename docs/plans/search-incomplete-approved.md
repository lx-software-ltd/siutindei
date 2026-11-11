# Plan: Show approved activities that lack a price or schedule

**Status**: Implemented
**Zone**: yellow

## Goal

Public search keeps today's rows for activities that have a schedule,
a schedule entry, and a price. When the caller sends
`include_incomplete=true`, search also returns activities of an
approved organization that are missing a price, a schedule, or both,
as long as they have an open venue. Callers that omit the flag keep
today's results, so older app builds do not receive null `pricing` or
`schedule`.

## Non-goals

- A `review_forced` column. Any approved organization qualifies,
  including one that was approved before a later import left an
  activity incomplete.
- Changing the approval blockers. Missing price and missing schedule
  still block a release unless `force` is set.
- Showing an activity that has no open venue.

## Files

- `backend/src/app/db/queries.py` (filter and cursor fields only)
- `backend/src/app/db/incomplete_search.py`
- `backend/src/app/api/search.py`
- `backend/src/app/api/search_page.py`
- `backend/src/app/api/search_validation.py`
- `backend/src/app/api/schemas.py`
- `backend/src/app/api/admin_org_review_actions.py`
- `tests/test_search_incomplete.py`
- `tests/test_search_validation.py`
- `docs/api/search.yaml`
- `docs/api/partner.yaml`
- `docs/api/admin.yaml`
- `docs/architecture/decisions.md`
- `apps/public_www/src/lib/activities/`
- `apps/public_www/src/components/`
- `apps/siutindei_app/lib/`

## Invariants this change preserves

- A request without `include_incomplete` returns the same rows as today.
  An incomplete-phase cursor is ignored unless the flag is set.
- An incomplete row is returned only for `review_status = approved`,
  even when the review gate is off.
- Pending categorisation, closed organizations, and closed venues stay
  out.
- Price, schedule, day, time, and language filters exclude an
  incomplete row that cannot satisfy them.
- One incomplete activity contributes one row. The venue is chosen
  among venues that match the area, price, schedule, day, and language
  filters: a schedule venue, then a priced venue, then a linked venue.
- Complete rows stay first. Incomplete rows follow, ordered by
  organization name, activity name, then activity id.
- A schedule with no day or time is shown as unconfirmed. The app
  chrome stays English, including those placeholders.

## Review follow-up

The venue rank used to run before the area and price filters, so a
Stanley search could miss an activity whose other venue ranked first.
The rank now sees only venues that satisfy those filters, and only
venues of approved organizations. API Gateway's search parameter list
is unchanged: stage caching is off, and `backend/infrastructure/**`
is red.

## Done when

`pytest tests/test_search_incomplete.py tests/test_search_validation.py`
passes. `python3 scripts/check_openapi_routes.py` passes.
`npm run typecheck` and `npm test` pass in `apps/public_www`.

## Rollback

Stop sending `include_incomplete` from the website and the app. Search
returns today's rows without a backend revert.

## Open questions

None.
