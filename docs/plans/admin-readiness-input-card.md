# Plan: Readiness as an input card

**Status**: Approved
**Zone**: yellow

## Goal

Make Readiness the same input card as Organization, workspace choose, and
manager pending tickets: `Card` (optional title and description) wrapping
`AdminEditorPanel` (fields, banners, action row). Login and dialog overlays
stay separate.

## Non-goals

- Changing review decide behavior, Fix deep links, or query params
- Restyling login or `AdminDialog`
- KPI, table, or map cards

## Files

- `apps/admin_web/src/components/admin/organization-readiness.tsx`
- `apps/admin_web/src/components/admin/workspace-empty.tsx`
- `apps/admin_web/src/components/shared/organizations-panel.tsx` (manager empty)
- Manager pending-ticket cards if their body is still a hand-rolled `dl`
- `.cursor/skills/admin-crud-screen/SKILL.md`, `docs/architecture/admin-web-ui.md`

## Invariants this change preserves

- Approve / Reject / Reopen and Approve anyway
- Fix links still change section / tab / org
- Workspace empty still opens Catalog

## Done when

- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Unit tests for Readiness and workspace choose as input cards
- Playwright org-review still finds the Readiness heading and actions

## Rollback

Revert the branch.

## Open questions

None. Approved in chat: Readiness becomes an input card; login and overlays
may stay different.
