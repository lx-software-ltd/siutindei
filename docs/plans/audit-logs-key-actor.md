# Plan: Audit log key actor names

**Status**: Done
**Zone**: yellow

## Goal

When an audit row's actor is a partner API key (`user_id` stored as
`api-key:<id>`), the Audit logs table and its expanded detail show
that key's name, with a key icon after the name. A known Cognito actor
shows the email and that user's sign-in icon. An unknown user id shows
an em dash and a person icon. An empty `user_id` shows `system` with a
gear, because that row is not always a migration. `category-scan:<run id>`
shows `category check`. Other `<name>:<id>` actors show the name and
hide the id. A failed key-name lookup is an error, not a silent dash.
Creating or revoking a key refreshes the name cache. An empty phone
caption keeps the icon.

## Non-goals

- Changing the stored `user_id` or the audit trigger.
- Adding an actor filter.
- Resolving key names on catalog versions or import changes.

## Files

- `apps/admin_web/src/lib/audit-actor.ts`
- `apps/admin_web/src/lib/admin-query-keys.ts`
- `apps/admin_web/src/lib/admin-query-client.ts`
- `apps/admin_web/src/components/admin/audit-logs-panel.tsx`
- `apps/admin_web/src/components/admin/api-keys-panel.tsx`
- `apps/admin_web/src/components/icons/action-icons.tsx`
- `apps/admin_web/tests/lib/audit-actor.test.ts`
- `apps/admin_web/tests/components/admin/audit-actor-value.test.tsx`
- `apps/admin_web/tests/components/admin/audit-logs-key-names.test.tsx`
- `apps/admin_web/e2e/audit-logs.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`
- `docs/architecture/audit-logging.md`
- `.cursor/skills/admin-crud-screen/SKILL.md`

## Invariants this change preserves

- The list still queries `GET /v1/admin/audit-logs`. Key names come
  from `GET /v1/admin/api-keys`, including revoked keys, so an old
  row can still name its key.
- The table does not print the raw `api-key:<id>` or a Cognito sub.
- An unknown user id is still an em dash, with a person icon. An
  unknown key id is an em dash with the key icon.
- Rows still expand in place. Icons sit after the text. The phone
  caption for an empty name is `Actor —` plus the icon.

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
