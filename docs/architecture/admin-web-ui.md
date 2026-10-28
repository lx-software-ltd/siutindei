# Admin web UI

The admin console is a table-first workspace. Section names live in the
nav. Listing cards do not repeat them. Workspace table sections show the
open organization above the card. The Organization page shows that
name and status badges above a Details input card.

The product rules live in `.cursor/skills/admin-crud-screen/SKILL.md`
and `.cursor/rules/admin-web.mdc`. This page names the primitives those
rules use.

## Page names

`formatAdminPageName(nav, tab)` in
`apps/admin_web/src/lib/admin-page-name.ts` is the page name.

- Nav only when there is no tab, or the tab is the default and repeats
  the nav (`Imports`, `Categories`, `Feedback`).
- Otherwise `Nav · Tab` (`Imports · History`, `Imports · Settings`,
  `Categories · Suggestions`, `Data quality · Names`).
- Do not invent fused phrases (`Import history`).
- Sub-tabs (Catalog Table / Map) are not part of the name.
- The table `aria-label` and the page's `sr-only` heading use that name.
  Sidebar shows nav; the strip shows the tab.

## Primitives

| Concern | Use |
| --- | --- |
| Page shell | Untitled `Card` (`AdminRecordTable`): optional filters left, optional actions left on a new row, table, optional Load more. Banners sit above the card |
| Input card | `AdminInputCard`: required title, variable content, and a bar when there are actions. A nested card uses `titleLevel="h3"`. Same `Card` chrome and title style. Login and dialog overlays stay on `Card`. Expanded row editors stay on `AdminEditorPanel` inside the table card. Post-submit results use `footer` |
| Create | `AdminCreateButton`, label `New <noun>`, on the table `actions` row. Same size as `Button` `md` (`h-10` below `sm`, `h-9` from `sm`, `w-auto`) |
| Bulk and scan actions | `actions` slot, left-aligned. Sweep pending and Sweep all orgs stay primary. Apply and Dismiss are `secondary`. The Catalog release toggle is a pressed `Button` on that row and clears after a successful bulk action. The header checkbox selects the visible page, then all matching rows. Scope filters stay in `AdminFilterBar`. Import and organization scope notes sit above the card with Show all. Catalog filters sit inside the table card. On Map, that same bar sits above the map card |
| Fields | `AdminField` inside `AdminFieldGrid` (1, 2, or 4 columns). Titles are `font-semibold` |
| Required mark and invalid border | `RequiredMark` and `formErrorClassName` from `admin-field-grid.tsx` |
| Field errors | `error` on `AdminField`, which renders `AdminInlineError` |
| Read-only values | `AdminReadOnlyValue` (`dl` / `dt` / `dd`, `span` 1, 2, or `full`) |
| Row operations | `AdminRowActions` (icon-only, tooltip, overflow menu) |
| Dialogs | `AdminDialog` with a header Close control. `ConfirmDialog` is the confirm/cancel footer. `footer={null}` keeps the header Close and omits the footer |
| Status chips | `StatusBadge` with an optional `tone` |
| Table cell content | One role per cell: `AdminTableName`, plain text, `AdminTableTime`, `StatusBadge`, `AdminTableId`, `AdminTableNumber`, or an em dash. Confidence is a percent. Hidden columns repeat under the name with `AdminDataTableCellMeta`; an empty caption includes the column name. Draft cells inherit header priority. Cell `className` is layout only |
| Banners | `StatusBanner` `kind` (`error`, `saved`, `pending-review`, `info`) sets the colour and default heading. `title` overrides the heading |
| In-area switchers | `AdminTabStrip` (sentence case) |
| Multi-select chips | `AdminToggleChip` |
| Icons | `src/components/icons/action-icons.tsx` |
| In-flight buttons | `Button` `loading` |

## Pre-auth surfaces

The signed-out login page and the session-loading state use the public
site's Small World backdrop: stacked logo, golden gradient, and a fixed
set of kawaii pictures. Brand colour tokens in
`apps/admin_web/src/app/globals.css` mirror
`apps/public_www/src/app/globals.css`. Change both or neither. The
signed-in console stays on the slate primitives below. There is no
environment label on the login pill.

## Exceptions

Organization media stays a drag-reorder grid. It uses the same save
button and banners as other editors. There is no Cancel control.
Leaving the section, or switching the open organization, deletes
uploads that were never saved.

The Users Email cell holds the email, the provider icon, and the
current-user You mark. Name and Created stay in the expanded row, not
in the listing.

## Guardrail

`apps/admin_web/eslint.config.js` rejects hand-rolled field errors whose
`className` combines `text-xs` or `text-sm` with `text-red-600` (one
string, a template, or split `clsx` arguments) and `<svg>` markup
outside `src/components/icons/`.
