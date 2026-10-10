# Plan: Skip existing rows on import

**Status**: Done
**Zone**: yellow

## Goal

Let an admin import a file without rewriting organizations, venues,
activities, pricing, or schedules that already exist. New rows are
still created. The API still updates when `allow_updates` is omitted.
The admin checkbox defaults to skip.

## Non-goals

- Changing merge. A merge still deletes the source organization.
- Matching activities by a stable source id.
- Adding a column on `import_jobs`. The flag is stored on the job
  summary JSON. Jobs without the key updated existing rows.

## Files

- `backend/src/app/api/admin_imports.py` parses `allow_updates`.
- `backend/src/app/api/admin_imports_upsert.py` and
  `backend/src/app/services/import_names.py` skip a cleaned activity
  name when updates are off.
- `docs/api/admin.yaml` and the generated admin types.
- `apps/admin_web` import form, client, and Playwright spec.
- `docs/architecture/overview.md` and
  `docs/architecture/data-quality.md` for the stale importer wording.
- `tests/test_admin_imports.py`.

## Invariants this change preserves

- Omitting `allow_updates` still updates a matching row.
- `manager_id` is never written on update. Update mode still rejects
  a different `manager_id`.
- Skip mode leaves an existing organization unchanged when
  `manager_id` is missing or different, and still imports missing
  children. A catalog row owned by the board manager still fails.
- The same uploaded `object_key` returns the stored job when
  `dry_run` and `allow_updates` match. A different flag runs again.
- Name cleanup on a normal import is unchanged.
- Skip mode does not join a skipped activity to the imported venue.
  A new activity still gets that join.

## Done when

- `pytest tests/test_admin_imports.py tests/test_import_names.py`
- `python3 scripts/check_openapi_routes.py`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/imports.spec.ts` in `apps/admin_web`
- `pre-commit run ruff-format --all-files` before the Python commit

## Rollback

Revert the branch. No schema change.

## Open questions

None. The checkbox defaults to checked and sends `allow_updates: false`.
History retry sends the stored flag.
