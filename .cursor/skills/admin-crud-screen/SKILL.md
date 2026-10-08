---
name: admin-crud-screen
description: Build or change an admin list screen using the table-first expand-in-place pattern.
---

# Admin CRUD screen

Build list screens from `apps/admin_web/src/components/ui/`.

- Page order is filters, then the table, inside one untitled white card (`AdminRecordTable`). Workspace pages show the open organization's name and status badges above that card. A new organization uses the heading "New organization" with no badges.
- Filters (`AdminFilterBar` + `AdminFilterField`) sit above the table. `AdminCreateButton` spells out its label at every breakpoint. Filters apply on change. Text filters are debounced. Do not render Apply or Clear.
- Rows expand in place (`AdminExpandableRow` + `useExpandedRecord`). One row is open. Do not put `border-x-*` on expandable rows. Create inserts a draft row (`DRAFT_RECORD_ID`, URL value `new`).
- Editors (`AdminEditorPanel` + `AdminEditorActions`) have no title and no Cancel button. Fields use `AdminField` inside `AdminFieldGrid`. Field errors are the `error` prop (`AdminInlineError`). Do not hand-write `text-xs` or `text-sm` with `text-red-600`. Read-only details use `AdminReadOnlyValue`. Unsaved edits use `AdminDiscardChangesDialog`.
- Banners use `StatusBanner` `kind`: `error`, `saved`, `pending-review`, `info`. Pass `title` only to override the heading. Do not also pass `variant`.
- Chips use `AdminToggleChip`. Bulk and scan actions go in the table `toolbar`.
- Dialogs use `AdminDialog`. `ConfirmDialog` is the confirm/cancel footer. `footer={null}` omits the footer.
- Operations use `AdminRowActions`. More than two actions: the first stays inline and the rest go in the menu. Tables with no row actions omit the Operations column.
- Mobile: no `min-w-*` on record tables. Non-essential columns use `priority='secondary'` or `priority='tertiary'`.
- In-flight buttons use `Button` `loading`. Loading tables use `AdminSkeletonRows`.
- Server state is TanStack Query via `getAdminQueryClient()`, `adminQueryKeys`, and `usePaginatedList`. `useResourceEditor` is the list and editor hook for resource-api screens.
- Read-only records still expand in place. Do not add a detail dialog for them.
- In-area switchers use `AdminTabStrip`. Tab labels are Title Case.
- Deep links use `?<entity>=<id>`. `org` is the workspace organization and stays across workspace sections. Legacy `?organization=` and `?edit=` still open that organization.
- Organization media stays a drag-reorder grid. There is no Cancel control. Leaving the section deletes uploads that were not saved.

## Done

`npm run lint` and `npm run typecheck` pass in `apps/admin_web`, and the Playwright spec for the screen matches the labels.
