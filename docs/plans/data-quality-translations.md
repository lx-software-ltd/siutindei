# Plan: Data quality Translations tab

**Status**: Accepted
**Zone**: yellow, plus one red migration under `backend/db/alembic/versions/`

## Decisions

1. Migration `0053_translation_fixes` is part of this request. It adds the sweep, proposal, and budget tables. `seed_data.sql` does not change. The migration inserts the settings singleton. The proposal and scan tables stay empty.
2. Required languages are English (`en`, the base column), Chinese (`zh`), and Hong Kong Chinese (`zh-HK`).
3. Fields are organization and activity `name` and `description`. A field is queued only when at least one of those three languages has text and at least one is missing. A blank description is not a translation task.
4. The model and fallbacks come from category-check settings. Spend counts toward `translation_fix_settings.monthly_cost_limit_usd` (default 50) and does not include category-check or location-sweep spend.
5. Apply writes only languages that are still missing. It does not replace text that is already stored. A dismissed proposal with the same source text is not queued again.

## Goal

Add a Data quality tab, Translations, that finds missing English, Chinese, or Hong Kong text and proposes the missing languages. Sweep pending covers organizations still in review. Sweep all orgs includes approved organizations. Admins apply or dismiss one row or the selected rows.

## Non-goals

- Partner API routes.
- Running this sweep from import data-quality checks.
- Translating categories, areas, locations, or languages other than `en`, `zh`, and `zh-HK`.
- Replacing a language that already has text.
- Editing `app.services.openrouter_client`.

## Files

- `backend/db/alembic/versions/0053_translation_fixes.py` (red)
- `backend/src/app/db/models/translation_fix.py`
- `backend/src/app/services/translation_gaps.py`
- `backend/src/app/services/translation_fix_scan.py`
- `backend/src/app/services/translation_fix_model.py`
- `backend/src/app/services/translation_fix_prompt.py`
- `backend/src/app/services/translation_fixes.py`
- `backend/src/app/services/translation_fix_query.py`
- `backend/src/app/api/admin_translation_fixes.py`
- `backend/lambda/category_suggestions/handler.py` (dispatch on `translation_scan_run_id`)
- `docs/api/admin.yaml`
- `apps/admin_web` tab, panel, client, and e2e fixture

## Invariants this change preserves

- OpenRouter calls stay inside `openrouter_client`.
- One translation sweep runs at a time.
- Category-check and location budgets are unchanged.
- Existing name, description, and translation values are not overwritten.

## Done when

`pytest tests/test_translation_gaps.py tests/test_translation_fixes.py tests/test_alembic_revision_contract.py` passes. Admin web lint, typecheck, and the Translations panel test pass. `python3 scripts/check_openapi_routes.py` passes.

## Rollback

Revert the commit. Downgrade drops `translation_fix_settings`, `translation_fix_proposals`, and `translation_scan_runs`.

## Follow-up

Sweep accounting, the model-batch helpers, and the admin list filters are shared with the location sweep. The review queue uses the same required-language gap as this tab.

The translation budget stays on its own tables. Location sweeps already persist to `location_fix_settings`, so folding both into one budget table would migrate data that is already shipped.

## Open questions

None.
