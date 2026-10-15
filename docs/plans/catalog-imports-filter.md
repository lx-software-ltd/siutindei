# Plan: Catalog imports filter

**Status**: Done
**Zone**: yellow

## Goal

The Catalog filter bar has an Imports menu after the organization
name. All imports shows every organization. The other choices are
the newest 20 live import jobs. Dry runs are skipped, and the menu
keeps reading later pages until it has 20 live jobs or the history
ends. Each choice's value is that job's `created_at`, and the label
is the same time shown elsewhere in admin. Choosing one lists the
organizations from that import on Table and Map.

## Non-goals

- A new review-list query parameter
- Changing Imports · History or the data-quality import menu
- Hiding failed live jobs from the 20

## Files

- `docs/plans/catalog-imports-filter.md`
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`

## Invariants this change preserves

- `?job=` still filters the catalog and still shows
  Filtered to this import
- The name filter stays immediately before Imports
- Source, neighbourhood, and sort filters stay where they are
- The review query still sends `import_job_id`, not the timestamp

## Done when

- The menu's first option is All imports and the rest use
  `created_at` as the option value
- The imports request asks for 20 jobs
- Dry-run timestamps are not options
- Selecting `2024-02-01T00:00:00Z` requests `import_job_id=job-1`
  and hides organizations that import did not touch
- The same choice stays selected on Map
- All imports clears the job filter
- `npx playwright test e2e/organizations.spec.ts e2e/org-review.spec.ts`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
