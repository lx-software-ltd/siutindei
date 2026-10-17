# Plan: Keep model rows when the reply is long or cut off

**Status**: Done
**Zone**: red (`openrouter_client.py`), yellow (enrichment services)

The requester approved the red-zone change in chat after the reply limit and reasoning settings were named as the follow-up.

## Goal

An enrichment run on a site with many venues, programs, fees, and class times returns location, activity, pricing, and schedule proposals, not only the organization fields and media read from page metadata.

After the deeper crawl shipped, a run on a 12-page site still returned no model rows. The crawl was good: venue, term, and program pages, about 67,000 prompt characters. The loss is in the reply.

- The prompt asked for a `{value, confidence, evidence}` object on every field of every row. For 7 venues, 12 programs, a fee table, and a timetable, that is roughly 10,000 output tokens.
- The default model, `qwen/qwen3-30b-a3b`, has a 40,960-token window shared by the prompt (about 20,000 tokens here), its reasoning, and the reply.
- A reply that stops before the closing brace does not parse, so `sheet_from_text` returned `{}` and every model row was lost without an error.
- The "model sheet checked" log line printed no counts. `StructuredLogFormatter` only prints a field named `extra`, so the keyword arguments were dropped.

## Non-goals

No `response_format` or structured-output setting. Other OpenRouter workloads send the same request as before. No change to the crawl, the proposal tables, or the admin screens. No change to the shared log formatter, because turning on every `extra=` in the backend could start printing values that were never reviewed for PII.

## Files

- `backend/src/app/services/enrichment/prompt.py`: list rows carry plain values with one `confidence`, `url`, and `quote` per row. Organization fields keep their own evidence. The prompt is also capped by an estimated token count, counting CJK characters as one token each, so a Chinese site cannot overflow a 40,960-token window.
- `backend/src/app/services/enrichment/sheet.py`: when the reply does not parse, keep every complete row before the cut and close the open brackets.
- `backend/src/app/services/enrichment/run.py`: one log line per model reply with `finish_reason`, reply length, and whether the sheet parsed whole, was repaired, or was empty. The existing "model sheet checked" line passes its counts so the formatter prints them.
- `backend/src/app/services/openrouter_client.py` (red): optional `max_tokens` and `reasoning_off` arguments. When set, the request carries `max_tokens` and `reasoning: {"enabled": false}`. Nothing changes for callers that leave them out.
- `backend/src/app/services/enrichment/run.py`: enrichment asks for a 12,000-token reply cap with reasoning off. A quick 400 or 404 refusal, from a model with mandatory reasoning or a shorter output limit, is retried once without them.
- `backend/src/app/services/enrichment/constants.py`: prompt budget of 20,000 estimated tokens and reply cap of 12,000. The estimate can run about 15% low, so prompt, instructions, and reply stay under a 40,960-token window.
- `tests/test_org_enrichment_reply.py`, `tests/test_openrouter_reply_room.py` (new).

## Invariants this change preserves

Every proposed value still needs a quote found on a fetched page, or it is marked unverified and capped at 0.5. Rows with no quote are still dropped. A row cut off mid-way is dropped, never half-kept. Logs carry counts and the finish reason only, no page text or contact details.

## Done when

- `pytest tests/test_org_enrichment_reply.py tests/test_openrouter_reply_room.py tests/test_org_enrichment_depth.py tests/test_org_enrichment.py tests/test_category_suggestions.py` passes.
- `pytest tests backend` passes on a freshly migrated Postgres.
- `pre-commit run` passes on the changed files.
- On the real crawled pages of the site that returned nothing, a reply cut off at a 4,096-token budget still yields locations and activities, and the compact shape is several times smaller than the old one.

## Rollback

Revert the commits. Stored runs and proposals are unchanged.

## Open questions

A model with a larger window for this workload would leave more room still. That is an admin setting, not a code change.
