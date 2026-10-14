# Plan: Hide Data quality · Categories org and current columns

**Status**: Active
**Zone**: yellow

## Goal

Remove Organization and Current from the Data quality · Categories
table, including the phone captions under the activity name.

Proposed, Verdict, Confidence, and Status stay. Apply, Dismiss, and
Revert stay on the row. The review API still returns `org_name` and
`current_category_name`.

## Non-goals

- Changing the review API payload or sweep dialog.
- Removing organization from the scoped-org note above the card.
- Adding org or current into the expanded rationale panel.

## Files

- `docs/plans/dq-categories-hide-org-current.md`
- `apps/admin_web/src/components/admin/category-suggestions/category-checks-table.tsx`
- `apps/admin_web/tests/components/admin/category-checks-panel.test.tsx`
- `apps/admin_web/e2e/category-suggestions.spec.ts`
- `apps/admin_web/e2e/table-cell-captions.spec.ts`

## Invariants this change preserves

- The table still lists Activity, Proposed, Verdict, Confidence, and
  Status.
- Phone captions still repeat the remaining hidden columns under the
  name (Proposed, then tertiary columns).
- Filters, KPI cards, sweep, and Apply / Dismiss stay as they are.

## Done when

- Unit and Playwright specs assert Organization and Current are gone
  from the table and captions, and Proposed remains.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- Browser check: Data quality · Categories no longer shows those
  columns.

## Rollback

Revert the pull request.

## Open questions

None.
