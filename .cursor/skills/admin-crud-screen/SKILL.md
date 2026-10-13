---
name: admin-crud-screen
description: Build or change an admin list screen using the table-first expand-in-place pattern.
---

# Admin CRUD screen

Build list screens from `apps/admin_web/src/components/ui/`.

- Page-level table cards are an untitled white `Card` (`AdminRecordTable`) with four slots: optional filters left, optional actions right on a **new** row, the table, optional Load more. Nothing else inside the card. Workspace pages show the open organization's name and status badges above that table card. The Organization input card puts the name and badges in the card title. A new organization uses the card title "New organization" with no badges.
- Filters (`AdminFilterBar` + `AdminFilterField`) are left-aligned fields only. `AdminCreateButton` spells out its label at every breakpoint and sits on the `actions` row. Filters apply on change. Text filters are debounced. Do not render Apply or Clear. Omit empty filter bars. Catalog filters stay above Table / Map as page chrome because they apply to both views.
- Rows expand in place (`AdminExpandableRow` + `useExpandedRecord`). One row is open. Do not put `border-x-*` on expandable rows. Create inserts a draft row (`DRAFT_RECORD_ID`, URL value `new`).
- Editors (`AdminEditorPanel` + `AdminEditorActions`) have no title and no Cancel button. Fields use `AdminField` inside `AdminFieldGrid`. Field errors are the `error` prop (`AdminInlineError`). Do not hand-write `text-xs` or `text-sm` with `text-red-600`. Read-only details use `AdminReadOnlyValue`. Unsaved edits use `AdminDiscardChangesDialog`.
- Input cards are `AdminInputCard`: required title (`text-base font-semibold sm:text-lg`), variable content, and a bar that always renders (`border-t border-slate-200 pt-4`). Card chrome is `Card`. Do not invent a dummy button when there is no action. Login and dialog overlays stay on `Card`. Expanded row editors stay on `AdminEditorPanel` inside the table card.
- Banners use `StatusBanner` `kind`: `error`, `saved`, `pending-review`, `info`. Pass `title` only to override the heading. Do not also pass `variant`.
- Chips use `AdminToggleChip`. Create, sweep, and bulk decide go in the table `actions` row (`justify-end`). Omit that row when there is no button. Banners, count lines, and Refreshing sit above the card.
- Dialogs use `AdminDialog`. `ConfirmDialog` is the confirm/cancel footer. `footer={null}` omits the footer.
- Operations use `AdminRowActions`. More than two actions: the first stays inline and the rest go in the menu. Tables with no row actions omit the Operations column.
- Mobile: no `min-w-*` on record tables. Non-essential columns use `priority='secondary'` or `priority='tertiary'`.
- In-flight buttons use `Button` `loading`. Loading tables use `AdminSkeletonRows`.
- Server state is TanStack Query via `getAdminQueryClient()`, `adminQueryKeys`, and `usePaginatedList`. `useResourceEditor` is the list and editor hook for resource-api screens.
- Read-only records still expand in place. Do not add a detail dialog for them.
- In-area switchers use `AdminTabStrip`. Tab labels are sentence case.
- Page name is the nav label when there is no tab, or the tab is the default and repeats the nav (`Imports`, `Categories`, `Feedback`). Otherwise the page name is `Nav · Tab` (`Imports · History`, `Categories · Suggestions`, `Data quality · Names`). Use `formatAdminPageName(nav, tab)` from `apps/admin_web/src/lib/admin-page-name.ts`. Do not invent fused phrases (`Import history`). Sub-tabs (Catalog Table / Map) are not part of the page name. Sidebar shows nav; the strip shows the tab. The table `aria-label` and the page's sr-only heading use the page name.
- Deep links use `?<entity>=<id>`. `org` is the workspace organization and stays across workspace sections. Legacy `?organization=` and `?edit=` still open that organization.
- Organization media stays a drag-reorder grid. There is no Cancel control. Leaving the section deletes uploads that were not saved.

## Done

`npm run lint` and `npm run typecheck` pass in `apps/admin_web`, and the Playwright spec for the screen matches the labels.
