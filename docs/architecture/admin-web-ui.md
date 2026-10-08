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
| Bulk and scan actions | `toolbar` slot. Sweep pending and Sweep all orgs stay primary. Apply and Dismiss follow. The header checkbox selects the visible page, then all matching rows. Scope filters stay in `AdminFilterBar` |
| Fields | `AdminField` inside `AdminFieldGrid` (1, 2, or 4 columns) |
| Required mark and invalid border | `RequiredMark` and `formErrorClassName` from `admin-field-grid.tsx` |
| Field errors | `error` on `AdminField`, which renders `AdminInlineError` |
| Read-only values | `AdminReadOnlyValue` (plain text, `span` 1, 2, or `full`) |
| Row operations | `AdminRowActions` (icon-only, tooltip, overflow menu) |
| Dialogs | `AdminDialog` with a header Close control. `ConfirmDialog` is the confirm/cancel footer. `footer={null}` keeps the header Close and omits the footer |
| Status chips | `StatusBadge` with an optional `tone` |
| Banners | `StatusBanner` `kind` (`error`, `saved`, `pending-review`, `info`) sets the colour and default heading. `title` overrides the heading |
| In-area switchers | `AdminTabStrip` (Title Case) |
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
