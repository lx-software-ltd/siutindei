# Plan: Sort categories by path then display order

**Status**: Accepted
**Zone**: yellow

## Goal

The Categories table lists rows in tree order: each parent, then its
children by `display_order` (then name). Path A order 1, then
A / A order 1, then A order 2.

## Non-goals

- Changing how `display_order` is stored or edited.
- Changing the public category tree API or wizard order.
- Backend list pagination order.

## Files

- `apps/admin_web/src/lib/activity-category-path.ts`
- `apps/admin_web/tests/lib/activity-category-path.test.ts`
- `apps/admin_web/src/components/shared/activity-categories-panel.tsx`
- `apps/admin_web/e2e/activity-categories.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`

## Invariants this change preserves

- Path labels still walk parent to child with ` / `.
- Sibling order stays `display_order`, then name, then id.
- A category whose parent is missing still appears (treated as a root).
- Create, edit, and delete stay on the same resource editor.

## Done when

- Unit tests cover the A 1 / A A 1 / A 2 order and a shuffled API list.
- Playwright asserts the Categories table row order.
- `npm run lint`, `npm run typecheck`, and `npm test` pass in
  `apps/admin_web`.

## Rollback

Revert the pull request.

## Open questions

None.
