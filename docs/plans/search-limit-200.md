# Plan: search accepts the documented limit of 200

**Status**: Done
**Zone**: yellow

## Goal

`GET /v1/partner/activities/search?limit=200` and the public search with
`limit=200` return a page instead of `400 limit must be between 1 and
200`. `search.yaml` and `partner.yaml` document 200 as the maximum.

The pager in `backend/src/app/api/search_page.py` asks the query for
`limit + 1` rows to learn whether another page exists. The query guard
`validate_filters` in `backend/src/app/db/queries.py` rejects anything
above 200, so a request for 200 asks for 201 and fails.

## Non-goals

- No change to the request bound. `search_validation.py` still rejects
  a requested `limit` above 200.
- No change to the Cloudflare `limit` allow-list on the public path.

## Files

- `backend/src/app/db/queries.py`: name the bound `MAX_SEARCH_LIMIT`,
  and let the query guard accept one probe row above it.
- `tests/test_search_page_limit.py`: database tests for `limit=200`,
  with and without incomplete rows, and on the incomplete phase.
- `tests/test_search_queries.py`: the guard accepts 201 and rejects 202.

## Invariants this change preserves

- A client still receives at most 200 items per page.
- Requests above 200 still return `400`.

## Done when

- `bash /tmp/run_backend_tests.sh tests/test_search_page_limit.py
  tests/test_search_queries.py` passes, and the new tests fail before
  the fix.
- The full backend suite passes.

## Rollback

Revert the commit. Requests for 200 return `400` again.

## Open questions

None.
