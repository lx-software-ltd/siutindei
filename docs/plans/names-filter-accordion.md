# Plan: Names filter and accordion actions

**Status**: Active
**Zone**: yellow

## Goal

On Data quality · Names, drop the Name text filter. Put Apply and
Dismiss on the expanded-row action bar so a `border-t` separator
precedes them, matching Pricing (`AdminEditorPanel` `actions`).

## Non-goals

- Changing list, sweep, or decide APIs
- Removing Record, Status, or Rule filters
- Changing Locations or other data-quality tabs

## Files

- `apps/admin_web/src/components/admin/data-quality/names-panel.tsx`
- `apps/admin_web/tests/components/admin/names-panel-settings.test.tsx`
- `apps/admin_web/e2e/data-quality.spec.ts`
- `apps/admin_web/e2e/table-card.spec.ts` (filters stay; Name input gone)

## Invariants this change preserves

- Record, Status, and Rule still filter the list.
- Sweep and bulk decide still work. Bulk "all matching" no longer
  sends `q` because the UI no longer has that filter.
- Apply and Dismiss still decide the open pending row.

## Done when

- Unit tests assert the Name input is gone and Apply / Dismiss sit
  on the editor action bar.
- Playwright asserts the same on the names tab.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- Browser check: filters have no Name field; expanding a row shows
  the separator above Apply / Dismiss.

## Rollback

Revert the commit.

## Open questions

None.
