# Plan: Read the pages that hold locations, programs, prices, and times

**Status**: Draft
**Zone**: yellow

## Goal

Enrichment proposes locations, activities, pricing, and schedules when the website lists them, not only organization fields and media.

A run on a youth basketball academy site showed two separate losses:

- The crawl spent its page budget on a photo gallery, a booking form, and a duplicate of the home page. It skipped the term, program, and policies pages. Each page started with the same navigation menu, and long pages were cut at 8000 characters before the prices and times.
- The venue page with eleven addresses reached the model, yet no location proposal came back. The model sheet is checked field by field, and each field must be an object with its own `value`, `confidence`, and `evidence`. Rows with evidence on the row, plain string fields, a `value` wrapper, a missing confidence, day names, or 12-hour times were dropped without a log line. A quote with different spacing or a URL without `www` or the trailing slash was marked unverified.

## Non-goals

No change to the settings table or its `max_pages <= 8` check (`backend/db/**` is red). No change to `openrouter_client.py`, `aws_proxy.py`, or the proxy Lambda. No PDF or JavaScript rendering.

## Files

- `backend/src/app/services/enrichment/constants.py`: link keywords, page text and prompt limits, crawl budget.
- `backend/src/app/services/enrichment/parse.py`: drop `<nav>` text but keep its links, rank links with positive and negative words, a URL key for duplicates.
- `backend/src/app/services/enrichment/fetch.py`: skip duplicate URLs and other-language copies of a page.
- `backend/src/app/services/enrichment/proxy_crawl.py`: allow the longer crawl budget.
- `backend/src/app/services/enrichment/sheet.py` (new): accept the row shapes models return, then check quotes with spacing, case, and URL differences ignored.
- `backend/src/app/services/enrichment/prompt.py` (new): instructions with a JSON example, and page text without repeated menus or footers.
- `backend/src/app/services/enrichment/extract.py`: use `sheet.py` and `prompt.py`.
- `backend/src/app/services/enrichment/run.py`: try every JSON candidate, and log page, prompt, and row counts per section.
- `tests/test_org_enrichment_depth.py` (new).

## Invariants this change preserves

Every proposed value still needs a quote that is on a fetched page, or it is marked unverified and capped at 0.5. The crawl stays on the seed site, honours robots.txt, waits between fetches, and refuses private addresses. Logs carry counts only, never page text or contact details.

## Done when

- `pytest tests/test_org_enrichment.py tests/test_org_enrichment_depth.py` passes. The new tests cover row-level evidence, the `value` wrapper, missing confidence, day names, 12-hour times, URL and spacing differences, `<nav>` stripping, link ranking, duplicate URLs, and prompt boilerplate.
- `pytest tests backend` passes on Postgres, and `pre-commit run` passes on the changed files.
- A live crawl of the reported site fetches its term, venue, and program pages within the default six pages.

## Rollback

Revert the commits. Existing runs and proposals are unchanged.

## Open questions

Going past eight pages needs a migration for the settings check (red zone).
