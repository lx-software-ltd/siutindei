# Plan: Audit logs table UX

**Status**: Accepted
**Zone**: yellow

## Goal

Tighten the Audit logs list and detail:

- Show action values in lowercase (`insert`, `update`, `delete`).
- Put the table filter before the action filter.
- Remove the actor email text filter.
- Show an em dash for a missing source, matching request id.
- Highlight changed tokens in old / new JSON with a darker
  background, using the evolvesprouts audit diff algorithm.

## Non-goals

- Changing stored `audit_log.action` values or the OpenAPI enum.
- Adding an actor filter of another kind.
- Serializing more audit fields on the backend.

## Files

- `apps/admin_web/src/components/admin/audit-logs-panel.tsx`
- `apps/admin_web/src/components/admin/audit-highlighted-json.tsx`
- `apps/admin_web/src/lib/audit-value-highlight.ts`
- `apps/admin_web/tests/lib/audit-value-highlight.test.ts`
- `apps/admin_web/tests/components/admin/audit-highlighted-json.test.tsx`
- `apps/admin_web/e2e/audit-logs.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`

## Invariants this change preserves

- The list still queries `GET /v1/admin/audit-logs` with uppercase
  `INSERT` / `UPDATE` / `DELETE` when an action filter is set.
- Actor emails still resolve in the Actor column via the Cognito
  directory. Only the email text filter goes away. The table prints
  the actor in the same body text as other cells, not as a monospace
  id.
- Rows still expand in place. There is no detail dialog.

## Done when

- Playwright `audit-logs.spec.ts` covers filter order, missing actor
  email input, lowercase actions, source dash, and changed-value
  highlight.
- `npm test`, `npm run lint`, and `npm run typecheck` pass in
  `apps/admin_web`.

## Rollback

Revert the pull request.

## Open questions

None.
