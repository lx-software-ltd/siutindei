# Plan: Admin review fixes

**Status**: Approved
**Zone**: yellow

## Goal

Close the regressions and leftovers found in the admin card series:

- Show the Catalog filter bar above the map card, using the same filter state.
- Show a media load error when the organization request fails.
- Show the settings error instead of a permanent "Loading settings..." line.
- Reset the Catalog release toggle after a bulk action.
- Hide the empty-table sentence when the list failed.
- Draw the input-card bar only when it has actions.
- Put the import result below the Upload & Import bar.
- Restore label and heading structure for screen readers.
- Give workspace tables the page-name heading, including manager Activities and Locations.
- Stop count lines, scope notes, placeholders, and the blank organization title from lying.
- Match create and other buttons on small screens, and let the release label wrap.

## Non-goals

- Editing `.github/workflows/**`. Those files are red. Playwright and typecheck stay local gates.
- Login and dialog chrome.
- Changing which fields a search matches.

## Files

- `apps/admin_web/src/components/ui/` card, input card, editor panel, record table, filter bar, create button, button, read-only value
- Catalog, media, settings, imports, readiness, workspace tables, data-quality count lines, category checks
- `apps/admin_web/src/lib/admin-page-name.ts`
- Admin web unit tests and Playwright specs
- `.cursor/skills/admin-crud-screen/SKILL.md`, `.cursor/rules/admin-web.mdc`, `docs/architecture/admin-web-ui.md`
- Mark `docs/plans/admin-table-card-style.md` superseded

## Invariants this change preserves

- Table cards keep four slots. Filters and actions stay left-aligned inside the table card.
- The map card does not contain a second copy of the filter bar.
- Operations do not toggle the row. Expanded editors stay inside the table card.
- Login and dialogs stay on `Card`.
- Page names still come from `formatAdminPageName`. No fused phrases.

## Done when

- `npm run lint`, `npm run typecheck`, and `npm run test` pass in `apps/admin_web`.
- Playwright covers the map filters, the release toggle, the import result order, and the renamed manager tables.
- `python3 scripts/validate_agent_rules.py` passes.

## Rollback

Revert this branch. No migration and no seed change.

## Open questions

None. The user asked for these fixes.
