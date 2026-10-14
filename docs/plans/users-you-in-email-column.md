# Plan: Users “You” mark in the Email column

**Status**: Implemented
**Zone**: yellow

## Goal

On the admin Users table, the current-user “You” mark sits in the
Email cell after the provider icon. Roles lists assigned roles only.

## Non-goals

- Changing how roles are granted, revoked, or deleted.
- Changing Cognito list or group APIs.
- Changing other admin tables.

## Files

- `docs/plans/users-you-in-email-column.md`
- `apps/admin_web/src/components/admin/cognito-users-panel.tsx`
- `apps/admin_web/e2e/cognito-users.spec.ts`
- `apps/admin_web/e2e/table-cell-captions.spec.ts`
- `.cursor/skills/admin-crud-screen/SKILL.md`
- `docs/architecture/admin-web-ui.md`

## Invariants this change preserves

- One row expands in place. Role grant, revoke, and delete stay on
  Operations.
- Users still cannot modify their own account.
- Provider stays the icon-valued status (`role="img"`) after the
  email.
- Hidden Roles and Last Login still repeat under the email on a phone.
- “You” remains a `StatusBadge`.

## Done when

- Playwright Users specs assert “You” is in the current user’s Email
  cell and not in Roles.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- A browser pass shows “You” after the provider on the signed-in row.

## Rollback

Revert the pull request.

## Open questions

None.
