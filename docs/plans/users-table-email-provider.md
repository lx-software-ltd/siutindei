# Plan: Users table email and detail fields

**Status**: Implemented
**Zone**: yellow

## Goal

Tighten the admin Users listing. Email and provider share one Email
column (`<email> <provider>`). Name and Created leave the table.
Username in the expanded row is an id. Name and provider follow
username in that accordion. Status renders in lowercase.

## Non-goals

- Changing how roles are granted, revoked, or deleted.
- Changing Cognito list or group APIs.
- Changing other admin tables.

## Files

- `docs/plans/users-table-email-provider.md`
- `apps/admin_web/src/components/admin/cognito-users-panel.tsx`
- `apps/admin_web/src/components/admin/cognito-users/badges.tsx`
- `apps/admin_web/e2e/cognito-users.spec.ts`
- `apps/admin_web/e2e/table-cell-captions.spec.ts`
- `.cursor/skills/admin-crud-screen/SKILL.md`
- `docs/architecture/admin-web-ui.md`

## Invariants this change preserves

- One row expands in place. Role grant, revoke, and delete stay on
  Operations.
- Users still cannot modify their own account.
- Provider stays the icon-valued status (`role="img"`).
- Hidden Roles and Last Login still repeat under the email on a phone.

## Done when

- Playwright Users specs match the new headers, merged email cell,
  accordion fields, and lowercase status.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- A browser pass confirms Name and Created are gone from the table,
  the email cell shows the provider icon, and the expanded row lists
  username (id), name, and provider after username.

## Rollback

Revert the pull request.

## Open questions

None.
