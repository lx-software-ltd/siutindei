# Plan: Places, categories, names, and logos from enrichment

**Status**: Done
**Zone**: yellow, plus one red allow-list line for the Meta graph

## Goal

A website-enrichment location stores a neighbourhood when the page or
a Nominatim pin can identify one. An activity stores a catalog
category when the name matches, and an unmatched wording becomes a
category suggestion on apply. An organization name is proposed only
while it is under review. A logo prefers a real logo on the site, then
the Facebook or Instagram picture from the existing Meta app.

## Non-goals

- Crawling facebook.com or instagram.com.
- A new `category_suggestions.source` value. That check allows only
  `import` and `scan`, and a new value would be a migration.
- Changing how imports resolve areas.
- Snapping a district to a neighbourhood when there is no pin.

## Files

- `backend/src/app/services/enrichment/places.py`
- `backend/src/app/services/enrichment/logos.py`
- `backend/src/app/services/enrichment/refine.py`
- `extract.py`, `prompt.py`, `sheet.py`, `parse.py`, `run.py`,
  `apply_rows.py`, `constants.py`
- `backend/infrastructure/lib/api-stack.ts` (graph URL and optional key)
- Admin proposal table, its test, and the organizations Playwright flow
- `tests/test_enrichment_place.py`

## Invariants this change preserves

- A location still requires a neighbourhood before it is saved.
- An approved organization still needs a chosen category before a new
  activity is saved.
- An approved organization's name is not proposed or written.
- A missing Nominatim answer or a missing Meta key does not fail the run.
- At most five Nominatim calls per extract, one second apart, and the
  place plus logo lookups share 20 seconds after the model call.
- The Meta key is sent as a bearer header, never in the URL. Instagram
  pictures need `META_INSTAGRAM_USER_ID`; Facebook does not.
- A category suggestion is captured only when the saved activity stays
  on the pending category and Imports is set to capture unknown categories.
- One apply can set one logo.

## Done when

- `pytest tests/test_enrichment_place.py tests/test_org_enrichment.py tests/test_org_enrichment_depth.py tests/test_org_enrichment_reply.py`
- `pre-commit run ruff-format --all-files`
- `npm run lint`, `npm run typecheck`, and the proposal vitest in
  `apps/admin_web`
- Playwright `applies enrichment with the fields the website left out`

## Rollback

Revert the branch. Proposals already applied stay applied. No
migration.

## Open questions

None. Nominatim runs during extract. Names change only while
`review_status` is `pending_review`. Logos use `META_GRAPH_API_KEY`.
Unmatched category wording is captured with source `import`.
