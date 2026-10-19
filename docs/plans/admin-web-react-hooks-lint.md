# Plan: Admin web React hooks lint for Next 16.4

**Status**: Implemented
**Zone**: yellow

## Goal

Make the admin web minor-and-patch bump (Next and `eslint-config-next` 16.4.0) pass `npm run lint`. The new `react-hooks/refs`, `react-hooks/set-state-in-effect`, and `react-hooks/use-memo` rules flag existing list and editor code.

## Non-goals

- Rewriting list screens onto a new data layer.
- Changing auth routes.
- Bumping public website dependencies.

## Files

- `apps/admin_web/src/hooks/use-paginated-list.ts`
- `apps/admin_web/src/hooks/use-resource-editor.tsx`
- `apps/admin_web/src/hooks/use-activities-by-mode.ts`
- `apps/admin_web/src/hooks/use-locations-by-mode.ts`
- `apps/admin_web/src/hooks/use-organizations-by-mode.ts`
- Admin screens that assign `ref.current` during render or call `setState` synchronously from an effect.
- `apps/admin_web/tests/hooks/use-paginated-list.test.tsx`

## Invariants this change preserves

- List cache identity stays on the explicit query key. Callers already put fetcher inputs in that key.
- Explicit refetch still reports loading while the first page is in flight.
- Latest organization, run, and filter values used by list fetchers stay current when those inputs change.
- Opening a proposal, ticket, or enrichment run still resets the local editor to that record.
- Loading flags still turn on when a request key changes and off when the request finishes.

## Done when

`npm run lint` and `npm run typecheck` pass in `apps/admin_web`. `npm test -- tests/hooks/use-paginated-list.test.tsx tests/hooks/use-resource-editor.test.tsx tests/components/admin/import-settings-panel.test.tsx tests/components/admin/locations-panel.test.tsx tests/components/admin/translations-panel.test.tsx tests/components/admin/organization-readiness.test.tsx tests/components/admin/category-checks-panel.test.tsx` passes.

## Rollback

Revert this change. The dependency bump can stay only if the lint rules are reverted with it.

## Open questions

None.
