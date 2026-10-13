# Plan: One table card style

**Status**: Approved
**Zone**: yellow

## Goal

Every page-level table card uses the same four slots and the same chrome:

1. Filters — optional. Left-aligned. `AdminFilterBar` fields only.
2. Actions — optional. A **new row**, right-aligned. Create, sweep,
   bulk decide. Buttons only.
3. Table — the record table.
4. Load more — optional. Under the table.

Nothing else lives inside the card. Card chrome is the untitled `Card`
already used by `AdminRecordTable`: white, `border-slate-200`,
`shadow-sm`, `rounded-lg` / `sm:rounded-xl`, `p-4` / `sm:p-6`.

Workspace org name stays **above** the card. KPI cards, tab strips,
map cards, and input cards stay separate. Expanded row editors stay
inside the table. Row checkboxes stay in the table. Login and dialogs
stay out.

Unlike `AdminInputCard`, omit the actions row when there is no button.
Do not invent a dummy button.

## Non-goals

- KPI, map, or input cards
- Changing list / query / create / sweep / bulk behavior
- Row operations (the Operations column)
- Moving Catalog filters into the table card (they apply to Map too)

## Proposed shape

```tsx
<AdminRecordTable
  filters={<AdminFilterBar>…fields…</AdminFilterBar>}
  actions={<>…buttons…</>}
  hasMore
  onLoadMore={…}
>
  {rows}
</AdminRecordTable>
```

- Drop `trailing` from `AdminFilterBar`. Filters are one left-aligned
  row. No summary line.
- Replace `toolbar` with `actions`: a row that renders only when there
  are buttons, `justify-end`, same `gap-2` as the input-card bar.
- Create, sweep, and bulk decide all go in `actions`.
- Banners, selection copy, count lines, and “Refreshing…” leave the
  card. Put them above the card (page chrome). Keep an `sr-only` busy
  status if needed. Drop unused `footer`.
- Empty filter bars go away. Create-only screens render the actions
  row only.
- Catalog: filters stay **outside** the table card, after the Table /
  Map switcher (they apply to both views). Create and bulk decide move
  into the table card `actions` row. Clear import filter stays with the
  Catalog page-chrome filters. The “Release even when…” checkbox stays
  on the actions row, to the left of those buttons. Consequence: New
  organization is Table-view only.
- Category-checks buttons drop `size='sm'` so they match Names /
  Locations.

Record the four slots in the admin CRUD skill,
`.cursor/rules/admin-web.mdc`, and
`docs/architecture/admin-web-ui.md`.

## Files

- `apps/admin_web/src/components/ui/admin-record-table.tsx`
- `apps/admin_web/src/components/ui/admin-filter-bar.tsx`
- `apps/admin_web/src/components/ui/resource-table-shell.tsx`
- Every `ResourceTableShell` call site
- Catalog `review-queue-panel.tsx`
- Unit tests for the four slots
- Playwright specs that look for Create on the filter row

## Invariants this change preserves

- Filter apply-on-change, debounce, no Apply / Clear (Clear import
  remains the Catalog exception)
- Create still opens a draft row (or Catalog workspace)
- Sweep / bulk / Load more behavior and query keys
- Workspace org heading still sits above table cards
- Catalog Table / Map still share the same filters
- Row checkboxes stay in the table leading column

## Done when

- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Unit tests for filter row left, actions row right, Load more last
- Playwright still finds New organization, Sweep pending, and Load more

## Rollback

Revert the branch.

## Open questions

None. Catalog filters stay outside the card. Omit the actions row
when there is no button. No dummy buttons.
