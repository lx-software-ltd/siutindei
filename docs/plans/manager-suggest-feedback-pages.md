# Plan: Manager Suggest a Place and Feedback pages

**Status**: Implemented
**Zone**: yellow

## Goal

A manager can open Suggest a Place and Feedback and stay there. Those
sections must not reload the account in a loop, and must not rewrite
the URL back to the organization workspace.

## Non-goals

- Changing admin Feedback, which still drops the workspace `org` param.
- Changing the user account home, which does not use the section query.
- Raising Lambda concurrency or editing alarms.

## Files

- `apps/admin_web/src/components/admin/admin-dashboard.tsx`
- `apps/admin_web/src/components/admin/manager-dashboard.tsx`
- `apps/admin_web/src/hooks/use-admin-section-query.ts`
- `apps/admin_web/src/lib/admin-section-params.ts`
- `apps/admin_web/tests/admin-section-params.test.ts`
- `apps/admin_web/tests/hooks/use-admin-section-query.test.tsx`
- `apps/admin_web/tests/components/admin/manager-suggest-feedback.test.tsx`
- `apps/admin_web/e2e/manager-dashboard.spec.ts`

## Invariants this change preserves

- Admin Feedback still clears `org` when the operator leaves the workspace.
- Workspace sections still keep `org` while moving among organization, media, locations, activities, pricing, and schedules.
- A manager section change still drops record params that section does not read (`location`, `ticket`, and the rest), except `org`.
- Account status still reloads when the selected organization id changes.

## Done when

`npm test -- tests/admin-section-params.test.ts tests/hooks/use-admin-section-query.test.tsx tests/components/admin/manager-suggest-feedback.test.tsx` passes in `apps/admin_web`. `npm run lint` and `npm run typecheck` pass there. Playwright `e2e/manager-dashboard.spec.ts` opens Suggest a Place and Feedback and leaves `org` in the URL.

## Rollback

Revert this change. No schema or seed change.

## Open questions

None.
