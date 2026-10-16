# Plan: Website enrichment review fixes

**Status**: Done
**Zone**: yellow, plus the unreleased `0055` grant in red `backend/db/**`

## Goal

Fix the enrichment review findings: form overwrite after apply, queue-before-commit, stuck runs, per-proposal apply failures, truncated images, media order, catalog-version reasons, duplicate proposals, apply order, missing override inputs, DNS rebinding, crawl deadlines, the admin grant, the saved website, the confidence floor, proposal readability, audit ids, per-host robots, and the JSON-LD cap.

## Non-goals

No change to the catalog version trigger function. The apply path sets the reason again before each proposal and stamps every catalog row from this transaction.

## Files

- `backend/src/app/services/enrichment/` — crawl, match, apply, run
- `backend/lambda/category_suggestions/handler.py` — commit, then queue
- `backend/db/alembic/versions/0055_org_enrichment.py` — grant
- `apps/admin_web/src/components/admin/organization-enrichment*.tsx`
- `apps/admin_web/src/hooks/use-resource-editor.tsx`
- `tests/test_org_enrichment.py` and `apps/admin_web/e2e/organizations.spec.ts`

## Invariants this change preserves

- Importer may start and read a run. Only an admin applies or dismisses.
- A proposal is written only after an admin accepts it.
- Model quotes still have to appear on a fetched page.
- The crawl still refuses private, loopback, and credentialed URLs.

## Done when

`pytest tests/test_org_enrichment.py` passes. Admin web lint, typecheck, and the organizations Playwright spec pass.

## Rollback

Revert the commit. The grant is in unreleased migration `0055`.

## Open questions

None.
