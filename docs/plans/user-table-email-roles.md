# Plan: Merge user table email and roles

**Status**: Accepted
**Zone**: yellow

## Goal

On the admin Users table, show assigned roles under the email instead of
a separate Roles column, swap Created and Last Login, and tidy the
expanded detail: drop raw attributes, colon-suffix labels, rename Groups
to Roles, and format the timestamps.

## Non-goals

- Changing how roles are granted or revoked.
- Showing unassigned roles as inactive badges.
- Changing other admin tables' detail labels.

## Files

- `docs/plans/user-table-email-roles.md`
- `apps/admin_web/src/components/admin/cognito-users-panel.tsx`
- `apps/admin_web/src/components/admin/cognito-users/badges.tsx`
- `apps/admin_web/e2e/cognito-users.spec.ts`

## Invariants this change preserves

- One row expands in place. Role grant, revoke, and delete stay on the
  Operations cell.
- Users still cannot modify their own account.
- Assigned admin and manager badges keep their current tones.

## Done when

- Playwright `e2e/cognito-users.spec.ts` matches the new headers, assigned
  roles only, and expanded labels.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- Browser pass confirms roles sit under email, inactive roles are absent,
  Created precedes Last Login, and the expanded row has no raw attributes.

## Rollback

Revert the pull request.

## Open questions

None.
