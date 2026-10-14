# Plan: Hide API key prefix and lowercase scope

**Status**: Implemented
**Zone**: yellow

## Goal

On the admin API keys table, drop the Prefix column (including its
phone caption) and show scope badges in lowercase (`read`, `crud`).

## Non-goals

- Changing how keys are created, revoked, or stored.
- Removing prefix from the expanded read-only detail.
- Changing StatusBadge capitalization for other tables.

## Files

- `docs/plans/api-key-table-prefix-scope.md`
- `apps/admin_web/src/components/admin/api-keys-panel.tsx`
- `apps/admin_web/e2e/api-keys.spec.ts`
- `apps/admin_web/e2e/table-cell-captions.spec.ts`

## Invariants this change preserves

- Scope stays a `StatusBadge` cell (blue for `read`, purple for `crud`).
- Organization, status, and expires columns stay in place.
- Prefix remains visible in the expanded row as a read-only field.
- A missing expiry is still an em dash, not “Never”.

## Done when

- Playwright `e2e/api-keys.spec.ts` and `e2e/table-cell-captions.spec.ts`
  assert no Prefix column and lowercase scope text.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- Browser pass confirms Prefix is gone from the listing and scope
  reads `read` / `crud`.

## Rollback

Revert the pull request.

## Open questions

None.
