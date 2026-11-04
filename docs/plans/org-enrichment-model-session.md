# Plan: Read the model settings on the enrichment session

**Status**: Implemented, not production-verified
**Zone**: yellow

## Goal

An enrichment extract starts the model call immediately, using the model, fallbacks, and data-collection flag saved in category-suggestion settings. A provider rejection on the last queue delivery tells the admin the provider was busy.

The admin database pool is one connection. Extract held that connection open, then `openrouter_chat_completion` opened three more sessions to load the same settings. Each waited out the 30 second pool timeout, the error was swallowed, and the call continued with the environment model and no fallbacks. Three waits are about 90 seconds. A 40 second model reply then landed after the 120 second function had been killed. The third delivery returned HTTP 429 in under a second and the run stored the generic "enrichment failed".

## Non-goals

No second paid model call after a 429. OpenRouter receives the configured fallbacks in the same request. No change to the crawl, the page cap, or the default `deny_data_collection` privacy setting. No change to `aws_proxy.py` or `openrouter_client.py`.

## Files

- `backend/src/app/services/enrichment/run.py`: read model settings on the open session and pass them through. A 408, 425, 429, or 5xx on the third delivery stores "The model provider was busy. Try again later."
- `apps/admin_web/src/components/admin/organization-enrichment.tsx`: "Reading the website…" while queued or crawling, "Reading pages with the model…" while extracting.
- `apps/admin_web/src/components/admin/category-suggestions/settings-card.tsx`: the model field says enrichment uses that model and needs a 40,960-token window.
- `docs/architecture/lambdas.md`: the one-connection rule for this call.
- `tests/test_org_enrichment.py`, `apps/admin_web/tests/components/admin/organization-enrichment-activity.test.tsx`, `apps/admin_web/e2e/organizations.spec.ts`.

## Invariants this change preserves

Proposals still need a quote on a fetched page. The model call stays one attempt plus the existing quick retry when a model rejects the reply cap. Logs carry the provider status, not page text or the API key. `deny_data_collection` stays whatever the settings row says, which defaults to deny.

## Done when

- `pytest tests/test_org_enrichment.py tests/test_org_enrichment_depth.py tests/test_org_enrichment_cache.py tests/test_org_enrichment_reply.py` passes. One extract test uses `pool_size=1`, `max_overflow=0`, `pool_timeout=1`. The last-delivery 429 test reads `run.error` from the database.
- `npm run test -- tests/components/admin/organization-enrichment-activity.test.tsx`, `npm run lint`, and `npm run typecheck` pass in `apps/admin_web`.
- The organizations Playwright spec covers the extracting sentence.
- `pre-commit run ruff-format --all-files` passes.
- After deploy, a re-run on the affected organization shows the proxy's `Proxying HTTP POST .../chat/completions` line within a few seconds of the extract job's `START`. That check is still outstanding.

## Rollback

Revert the commits. No schema or infrastructure change.

## Open questions

If a run still ends with the busy message after this, the provider rejected the configured model and its fallbacks. Change those in the category-suggestion settings. Leaving data-collection deny on is the privacy default; turning it off is an admin choice, not a code fallback. The prompt and reply caps assume a 40,960-token window; a smaller saved model can cut the reply.
