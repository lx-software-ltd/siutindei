# Plan: Left-align table actions; Catalog filters in the card

**Status**: Approved
**Zone**: yellow

## Goal

Action buttons on the table card sit on the left, same as the
filters. Catalog filters live inside the table card, not above it.

Map still uses the same filter state. The filter bar is not shown on
the map card.

## Non-goals

- Changing filter, create, sweep, or bulk behavior
- KPI, map, or input cards

## Files

- `apps/admin_web/src/components/ui/admin-record-table.tsx`
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
- Unit and Playwright slot tests
- CRUD skill, `admin-web.mdc`, `docs/architecture/admin-web-ui.md`

## Invariants this change preserves

- Four slots: filters, then actions, then table, then Load more
- Catalog Table / Map still share filter state
- Create / sweep / bulk still work

## Done when

- Unit test expects `justify-start` on the actions row
- Playwright: Catalog filter bar is inside the table card
- Playwright: New activity / New organization sit on the left

## Rollback

Revert the branch.
