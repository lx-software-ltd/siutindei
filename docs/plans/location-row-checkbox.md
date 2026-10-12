# Plan: Data quality location row checkbox

**Status**: Accepted
**Zone**: yellow

## Goal

Ticking one row on Data quality → Locations selects only that row.
Names and Categories share the same header/row selection model and
must keep the same rule.

## Non-goals

- Changing header-checkbox cycling (visible page, then all matching).
- Changing bulk apply/dismiss payloads.

## Files

- `apps/admin_web/src/hooks/use-bulk-row-selection.ts` (new)
- `apps/admin_web/src/components/admin/data-quality/locations-panel.tsx`
- `apps/admin_web/src/components/admin/data-quality/names-panel.tsx`
- `apps/admin_web/src/components/admin/category-suggestions/category-checks-panel.tsx`
- Tests under `apps/admin_web/tests` and `apps/admin_web/e2e`

## Invariants this change preserves

- Header checkbox still selects the visible page, then all matching
  rows when more pages exist.
- Bulk apply/dismiss still sends `ids` for a partial selection and
  filters (no `ids`) when the scope is all matching rows.
- Filter changes still clear the selection.

## Done when

- Unit tests show one row tick does not check the other rows.
- Header-checkbox cycle tests still pass.
- `npm run test`, `npm run lint`, and `npm run typecheck` pass in
  `apps/admin_web`.
- Playwright `data-quality.spec.ts` covers a single-row tick.

## Rollback

Revert the pull request.

## Open questions

None.
