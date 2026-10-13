# Plan: Admin view consolidation

**Status**: Approved
**Zone**: yellow

## Goal

Tighten admin list and form chrome: unlabeled filters with sentence-case empty options, consistent `Oct 13` / `Oct 13, 02:36 PM` timestamps, no Version table columns, expand-on-row-click including Operations padding, and clearer Imports / Organization / Audit copy.

Follow-up: Feedback tab `Labels`; drop Suggestions helper copy; Catalog filters and New organization live inside the table card. Page shape is tabs (if any), then a table card of filter row / action row / table / Load more, then titled cards.

Follow-up: every page surface (table, form, KPI, empty, after-table) uses the `Card` primitive / `cardSurfaceClass`. Do not hand-write `rounded-lg border border-slate-200 bg-white`.

Follow-up: page names use `formatAdminPageName`. Nav only when there is no tab, or the tab repeats the nav. Otherwise `Nav · Tab`. No fused phrases. Sub-tabs are not part of the name.

## Non-goals

- Backend audit serialization or catalog-version APIs
- Removing VersionHistory from expanded editors
- Changing filter query params or default values

## Files

- `apps/admin_web/src/lib/date-utils.ts` and list/detail call sites
- `apps/admin_web/src/lib/admin-page-name.ts` and list/detail call sites
- `apps/admin_web/src/components/ui/admin-expandable-row.tsx`
- Imports, catalog, workspace tables, data quality, categories, audit, users, tickets, API keys
- Playwright specs that assert the old labels, Version columns, timestamps, or fused page names
- `.cursor/skills/admin-crud-screen/SKILL.md`, `.cursor/rules/admin-web.mdc`, `docs/architecture/admin-web-ui.md`

## Invariants this change preserves

- Filter query keys and apply-on-change behavior
- Skip-existing import checkbox and `allow_updates`
- One expanded row; Operations buttons still do not toggle the row
- Deep links (`org`, `tab`, `suggestion`, `audit-log`)

## Done when

- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Targeted unit tests for dates, expandable-row click, audit actor, and page names
- Playwright specs match the new labels and `Nav · Tab` page names

## Rollback

Revert the branch.

## Open questions

None. Approved in chat with History When as datetime, sentence-case dropdowns, Audit Timestamp/Actor, and `migration` when `user_id` is empty.
