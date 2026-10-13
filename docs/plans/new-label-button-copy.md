# Plan: New label button copy

**Status**: Accepted
**Zone**: yellow

## Goal

The Feedback → Labels create control reads **New label**, matching
other admin create buttons (`New category`, `New location`).

## Non-goals

- Changing the labels table, editor, or API.
- Renaming the Feedback → Labels tab or page name.

## Files

- `apps/admin_web/src/components/admin/feedback-labels-panel.tsx`
- `apps/admin_web/e2e/feedback.spec.ts`

## Invariants this change preserves

- Create still opens a draft row. Only the visible label changes.
- The draft row label matches the button, as on other resource screens.

## Done when

- Playwright `feedback.spec.ts` looks for **New label**.
- The create button and draft row both say **New label**.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.

## Rollback

Revert the pull request.

## Open questions

None.
