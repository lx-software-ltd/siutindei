# Plan: Audit log key actor names

**Status**: Done
**Zone**: yellow

## Goal

When an audit row's actor is a partner API key (`user_id` stored as
`api-key:<id>`), the Audit logs table and its expanded detail show
that key's name, with a key icon after the name. A Cognito actor still
shows the email. An empty `user_id` still shows `migration`.

## Non-goals

- Changing the stored `user_id` or the audit trigger.
- Adding an actor filter.
- Resolving key names on catalog versions or import changes.

## Files

- `apps/admin_web/src/lib/audit-actor.ts`
- `apps/admin_web/src/components/admin/audit-logs-panel.tsx`
- `apps/admin_web/src/components/icons/action-icons.tsx`
- `apps/admin_web/tests/lib/audit-actor.test.ts`
- `apps/admin_web/e2e/audit-logs.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`
- `docs/architecture/audit-logging.md`
- `.cursor/skills/admin-crud-screen/SKILL.md`

## Invariants this change preserves

- The list still queries `GET /v1/admin/audit-logs`. Key names come
  from `GET /v1/admin/api-keys`, including revoked keys, so an old
  row can still name its key.
- The table does not print the raw `api-key:<id>` or a Cognito sub.
- An unknown user id is still an em dash. An unknown key id is an em
  dash with the key icon, so the actor kind stays visible.
- Rows still expand in place. The icon sits after the name, the same
  place as the Users provider icon, and uses `role="img"`.

## Done when

- `audit-actor.test.ts` covers a resolved key name, a blank name, and
  an unknown key id.
- Playwright `audit-logs.spec.ts` shows the key name and the API key
  icon, and does not show the raw id. Its table filter lists the same
  names as `AUDITABLE_TABLES`, including `cognito_user` and
  `import_settings`.
- `npm test`, `npm run lint`, and `npm run typecheck` pass in
  `apps/admin_web`.

## Rollback

Revert the pull request.

## Open questions

None.
