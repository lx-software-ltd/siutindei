# Plan: Import history entity links

**Status**: Done
**Zone**: yellow

## Goal

On Imports → History, each expanded result whose stored `id` still
points at a live row links to that organization, location, activity,
pricing, or schedule in the workspace.

## Non-goals

- Adding `org_id` to the import API or rewriting stored jobs.
- Linking dry-run ids (those rows were rolled back).
- Changing Mode, retry, View orgs, or the file download link.

## Files

- `docs/plans/import-history-entity-links.md`
- `apps/admin_web/src/lib/import-job-results.ts`
- `apps/admin_web/tests/lib/import-job-results.test.ts`
- `apps/admin_web/src/components/admin/org-review/import-history-panel.tsx`
- `apps/admin_web/e2e/org-review.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`

## Invariants this change preserves

- A result without an `id` stays plain text.
- A dry run still says predicted outcomes and does not link keys.
- Child links need the parent organization. The helper finds it from
  `path` (`organizations[n]…`) or from a `key` prefix (`Org / …`).
- File still opens from the expanded row without collapsing it.
- Failed notes, captured categories, and Mode labels are unchanged.

## Done when

- `npm test -- tests/lib/import-job-results.test.ts` in `apps/admin_web`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- `npx playwright test e2e/org-review.spec.ts` in `apps/admin_web`

## Rollback

Revert the branch. No schema change.

## Open questions

None. Workspace URLs are `?section=` plus `org` and the entity param
already used by the organization, location, activity, pricing, and
schedule panels.
