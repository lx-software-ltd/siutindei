# Plan: Schedule language flag for zh-HK

**Status**: Done
**Zone**: yellow

## Goal

Class schedules store a spoken language (`en`, `zh`, `yue`, and the
other ISO codes). Website enrichment was writing the translation
locale `zh-HK` instead. The admin Schedules table only has flags for
`en`, `zh`, and `yue`, so those rows show the text `zh-HK`.

Store that Hong Kong locale as `yue` on schedule writes, including
enrichment. Show a stored `zh-HK` with the same Hong Kong flag as
`yue`, and keep it selected in the editor so the next save persists
`yue`.

## Non-goals

- A migration or backfill. `backend/db/**` is red. Rows already stored
  as `zh-HK` stay until the next schedule write.
- Changing translation maps. Names and descriptions still use `zh-HK`.
- Remapping the public search language filter. Search still validates
  each code on its own, so a `zh-HK` filter is not a `yue` filter.

## Files

- `backend/src/app/api/admin_validators.py` — `schedule_languages`
  maps `zh-HK` and `zh_HK` to `yue`. `_validate_languages` does not.
  `comparable_schedule_languages` folds stored codes without rejecting
  unknown ones.
- `backend/src/app/db/repositories/schedule.py` — lookup compares
  folded language lists, so a stored `zh-HK` row matches a `yue` write.
- `backend/src/app/api/admin_resource_schedule.py` and
  `backend/src/app/api/admin_imports_schedule.py` — writes go through
  `schedule_languages`.
- `backend/src/app/services/enrichment/extract.py` — new schedule
  proposals use `yue`.
- `backend/src/app/services/enrichment/apply_rows.py` — apply stores
  `schedule_languages`, default `yue`.
- `backend/src/app/services/enrichment/match.py` — a stored `zh-HK`
  schedule matches a `yue` proposal, so a later crawl does not insert
  a second row.
- `apps/admin_web/src/components/shared/schedules/schedule-form-utils.ts`
  — table marks and the editor treat `zh-HK` as `yue`.
- `apps/admin_web/src/components/shared/schedules-panel.tsx` — render
  those marks.
- `docs/api/admin.yaml` — schedule requests accept `zh-HK` and
  `zh_HK` and store them as `yue`.
- Tests in `tests/test_admin_security_validation.py`,
  `tests/test_admin_imports.py`, `tests/test_org_enrichment.py`,
  `tests/test_org_enrichment_depth.py`,
  `apps/admin_web/tests/components/shared/schedule-form-utils.test.ts`,
  and the schedules Playwright spec.

## Invariants this change preserves

- Translation maps still accept and return `zh-HK`.
- Uniqueness stays activity + location + language list. Import,
  manual create, and enrichment compare that list after `zh-HK` is
  folded to `yue`.
- A stored language outside the allowed list does not raise during
  enrichment matching.
- An unknown schedule code still renders as text.

## Done when

- `pytest tests/test_admin_security_validation.py tests/test_admin_imports.py tests/test_org_enrichment.py tests/test_org_enrichment_depth.py`
- `npm test -- tests/components/shared/schedule-form-utils.test.ts`,
  `npm run lint`, and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/schedules.spec.ts` in `apps/admin_web`
- `pre-commit run ruff-format --all-files` before the Python commit

## Rollback

Revert the commit. Stored `zh-HK` rows are unchanged. The table shows
that code as text again, and a new enrichment schedule would store
`zh-HK` again.

## Open questions

None. Existing `zh-HK` schedule rows change only when something writes
that schedule again.
