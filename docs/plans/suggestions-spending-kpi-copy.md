# Plan: Suggestions spending KPI copy

**Status**: Active
**Zone**: yellow

## Goal

Rename the Categories · Suggestions spending tile from `Spending` to
`Spending per month` so the monthly window is in the label.

## Non-goals

- Changing the dollar value, summary API, or other KPI labels
- Adding a spending limit to the tile

## Files

- `apps/admin_web/src/components/admin/category-suggestions/category-suggestions-panel.tsx`
- `apps/admin_web/e2e/category-suggestions.spec.ts`
- `docs/plans/suggestions-kpi-cards.md`

## Invariants this change preserves

- Three `AdminKpiCard` tiles stay above the table card.
- Pending, activity, and spend values stay the same.

## Done when

- Playwright asserts `Spending per month`.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.

## Rollback

Revert the commit.

## Open questions

None.
