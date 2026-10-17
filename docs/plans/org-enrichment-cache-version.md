# Plan: Do not reuse a model result made by older extraction code

**Status**: Done
**Zone**: yellow

## Goal

Running enrichment again after the extraction code changes asks the model again, instead of copying the proposals of an earlier run that read the same pages.

After #712 deployed, a run at 14:18 UTC crawled for 14 seconds and finished one second later with no OpenRouter call and no "Enrichment model reply" log line. `_copy_cached` matched the 13:48 run: same organization, same page text hash, status `ready`. It copied that run's proposals, which were empty for every model section because that run's reply had been lost. The card showed organization fields and media only, again.

## Non-goals

No change to the proposal tables or the admin card. No change to how a run is started.

## Files

- `backend/src/app/services/enrichment/run.py`: `input_hash` covers the page text and an extraction version. The version is a hash of the model instructions plus a constant bumped when the parser or validator changes. Old `ready` runs keep their old hash and no longer match.
- `backend/src/app/services/enrichment/constants.py`: `EXTRACTION_VERSION`.
- `tests/test_org_enrichment_cache.py` (new).

## Invariants this change preserves

A second run on unchanged pages with unchanged extraction code still costs nothing: it copies the previous proposals. The cached copy still records `model = "cache"` and zero cost.

## Done when

- `pytest tests/test_org_enrichment_cache.py tests/test_org_enrichment.py` passes.
- `pytest tests backend` passes on a freshly migrated Postgres.
- `pre-commit run` passes on the changed files.

## Rollback

Revert the commit. Runs made in between carry the versioned hash and are simply never reused.

## Open questions

None.
