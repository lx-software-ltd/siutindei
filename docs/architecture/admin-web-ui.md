# Admin web UI

The admin console is a table-first workspace. Section names live in the
nav. Listing cards do not repeat them. Workspace sections show the open
organization above the card.

The product rules live in `.cursor/skills/admin-crud-screen/SKILL.md`
and `.cursor/rules/admin-web.mdc`. This page names the primitives those
rules use.

## Page names

`formatAdminPageName(nav, tab)` in
`apps/admin_web/src/lib/admin-page-name.ts` is the page name.

- Nav only when there is no tab, or the tab is the default and repeats
  the nav (`Imports`, `Categories`, `Feedback`).
- Otherwise `Nav · Tab` (`Imports · History`, `Categories · Suggestions`,
  `Data quality · Names`).
- Do not invent fused phrases (`Import history`).
- Sub-tabs (Catalog Table / Map) are not part of the name.
- The table `aria-label` and the page's `sr-only` heading use that name.
  Sidebar shows nav; the strip shows the tab.

## Primitives

| Concern | Use |
| --- | --- |
| Page shell | Filters, then the table, inside one untitled `Card` (`AdminRecordTable`) |
| Input card | `AdminInputCard`: required title, variable content, and a bar that always renders. Same `Card` chrome and title style. Login and dialog overlays stay on `Card`. Expanded row editors stay on `AdminEditorPanel` inside the table card |
| Create | `AdminCreateButton`, label `New <noun>`, trailing slot of `AdminFilterBar` |
| Bulk and scan actions | `toolbar` slot. Sweep pending and Sweep all orgs stay primary. Apply and Dismiss follow. The header checkbox selects the visible page, then all matching rows. Scope filters stay in `AdminFilterBar` |
| Fields | `AdminField` inside `AdminFieldGrid` (1, 2, or 4 columns) |
| Required mark and invalid border | `RequiredMark` and `formErrorClassName` from `admin-field-grid.tsx` |
| Field errors | `error` on `AdminField`, which renders `AdminInlineError` |
| Read-only values | `AdminReadOnlyValue` (plain text, `span` 1, 2, or `full`) |
| Row operations | `AdminRowActions` (icon-only, tooltip, overflow menu) |
| Dialogs | `AdminDialog` with a header Close control. `ConfirmDialog` is the confirm/cancel footer. `footer={null}` keeps the header Close and omits the footer |
| Status chips | `StatusBadge` with an optional `tone` |
| Banners | `StatusBanner` `kind` (`error`, `saved`, `pending-review`, `info`) sets the colour and default heading. `title` overrides the heading |
| In-area switchers | `AdminTabStrip` (sentence case) |
| Multi-select chips | `AdminToggleChip` |
| Icons | `src/components/icons/action-icons.tsx` |
| In-flight buttons | `Button` `loading` |

## Exceptions

Organization media stays a drag-reorder grid. It uses the same save
button and banners as other editors. There is no Cancel control.
Leaving the section, or switching the open organization, deletes
uploads that were never saved.

## Guardrail

`apps/admin_web/eslint.config.js` rejects hand-rolled field errors whose
`className` combines `text-xs` or `text-sm` with `text-red-600` (one
string, a template, or split `clsx` arguments) and `<svg>` markup
outside `src/components/icons/`.
