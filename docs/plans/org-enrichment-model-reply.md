# Plan: Keep model rows when the reply is long or cut off

**Status**: Done
**Zone**: yellow

## Goal

An enrichment run on a site with many venues, programs, fees, and class times returns location, activity, pricing, and schedule proposals, not only the organization fields and media read from page metadata.

After the deeper crawl shipped, a run on a 12-page site still returned no model rows. The crawl was good: venue, term, and program pages, about 67,000 prompt characters. The loss is in the reply.

- The prompt asked for a `{value, confidence, evidence}` object on every field of every row. For 7 venues, 12 programs, a fee table, and a timetable, that is roughly 10,000 output tokens.
- The default model, `qwen/qwen3-30b-a3b`, has a 40,960-token window shared by the prompt (about 20,000 tokens here), its reasoning, and the reply.
- A reply that stops before the closing brace does not parse, so `sheet_from_text` returned `{}` and every model row was lost without an error.
- The "model sheet checked" log line printed no counts. `StructuredLogFormatter` only prints a field named `extra`, so the keyword arguments were dropped.

## Non-goals

No change to `openrouter_client.py` (red), so no `max_tokens`, reasoning, or `response_format` setting in this change. No change to the crawl, the proposal tables, or the admin screens. No change to the shared log formatter, because turning on every `extra=` in the backend could start printing values that were never reviewed for PII.

## Files

- `backend/src/app/services/enrichment/prompt.py`: list rows carry plain values with one `confidence`, `url`, and `quote` per row. Organization fields keep their own evidence. The prompt is also capped by an estimated token count, counting CJK characters as one token each, so a Chinese site cannot overflow a 40,960-token window.
- `backend/src/app/services/enrichment/sheet.py`: when the reply does not parse, keep every complete row before the cut and close the open brackets.
- `backend/src/app/services/enrichment/run.py`: one log line per model reply with `finish_reason`, reply length, and whether the sheet parsed whole, was repaired, or was empty. The existing "model sheet checked" line passes its counts so the formatter prints them.
- `backend/src/app/services/enrichment/constants.py`: the prompt token budget.
- `tests/test_org_enrichment_reply.py` (new).

## Invariants this change preserves

Every proposed value still needs a quote found on a fetched page, or it is marked unverified and capped at 0.5. Rows with no quote are still dropped. A row cut off mid-way is dropped, never half-kept. Logs carry counts and the finish reason only, no page text or contact details.

## Done when

- `pytest tests/test_org_enrichment_reply.py tests/test_org_enrichment_depth.py tests/test_org_enrichment.py` passes.
- `pytest tests backend` passes on a freshly migrated Postgres.
- `pre-commit run` passes on the changed files.
- On the real crawled pages of the site that returned nothing, a reply cut off at a 4,096-token budget still yields locations and activities, and the compact shape is several times smaller than the old one.

## Rollback

Revert the commits. Stored runs and proposals are unchanged.

## Open questions

Setting `max_tokens` and turning reasoning off for this workload would leave more room for the reply. Both need a change in `openrouter_client.py`, which is red, so they are left for an approved follow-up.
