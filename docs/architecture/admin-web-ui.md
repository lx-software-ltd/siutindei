# Admin web UI

The admin console is a table-first workspace. Section names live in the
nav. Listing cards do not repeat them. Screen readers still get an
`sr-only` heading with the nav label. Workspace sections show the open
organization above the card.

The product rules live in `.cursorrules` under **Admin Web CRUD UX
pattern**. This page names the primitives those rules use.

## Primitives

| Concern | Use |
| --- | --- |
| Page shell | Filters, then the table, inside one untitled `Card` (`AdminRecordTable`) |
| Create | `AdminCreateButton`, label `New <noun>`, trailing slot of `AdminFilterBar` |
| Bulk and scan actions | `toolbar` slot on `AdminRecordTable` / `ResourceTableShell` |
| Fields | `AdminField` inside `AdminFieldGrid` (1, 2, or 4 columns) |
| Required mark and invalid border | `RequiredMark` and `formErrorClassName` from `admin-field-grid.tsx` |
| Field errors | `error` on `AdminField`, which renders `AdminInlineError` |
| Read-only values | `AdminReadOnlyValue` |
| Row operations | `AdminRowActions` (icon-only, tooltip, overflow menu) |
| Dialogs | `AdminDialog`. `ConfirmDialog` is the confirm/cancel footer on that shell |
| Status chips | `StatusBadge` with an optional `tone` |
| Banners | `StatusBanner` `kind`: `error`, `saved`, `pending-review`, `info` |
| In-area switchers | `AdminTabStrip` (Title Case) |
| Multi-select chips | `AdminToggleChip` |
| Icons | `src/components/icons/action-icons.tsx` |
| In-flight buttons | `Button` `loading` |

## Exceptions

Organization media stays a drag-reorder grid. It uses the same save
button and banners as other editors. Leaving the section drops unsaved
media edits; there is no Cancel control.

## Guardrail

`apps/admin_web/eslint.config.js` rejects hand-rolled
`text-xs text-red-600` field errors and `<svg>` markup outside
`src/components/icons/`.
