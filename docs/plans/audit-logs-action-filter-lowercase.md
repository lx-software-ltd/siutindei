# Plan: Lowercase audit log action filter values

**Status**: Accepted
**Zone**: yellow

## Goal

Show the Audit logs Action filter options in lowercase (`insert`,
`update`, `delete`) so the dropdown matches the table filter and the
already-lowercase action badges.

## Non-goals

- Changing stored `audit_log.action` values or the OpenAPI enum.
- Changing "All actions" or other filter labels.

## Files

- `apps/admin_web/src/components/admin/audit-logs-panel.tsx`
- `apps/admin_web/e2e/audit-logs.spec.ts`

## Invariants this change preserves

- The list still queries `GET /v1/admin/audit-logs` with uppercase
  `INSERT` / `UPDATE` / `DELETE` when an action filter is set.
- Action badges and expanded-row Action still display lowercase.

## Done when

- The Action filter option values and labels are `insert`, `update`,
  and `delete`.
- Playwright `apps/admin_web/e2e/audit-logs.spec.ts` asserts those
  labels and still filters by `update`.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.

## Rollback

Revert the commit.

## Open questions

None.
