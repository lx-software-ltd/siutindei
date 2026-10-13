# Plan: One table card style

**Status**: Draft
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

## Deviations today

`AdminRecordTable` already stacks `filters` → `toolbar` → table →
Load more. Almost no surface matches the four-slot rule.

| Surface | Filters | Actions | Extra in the card | What is off |
| --- | --- | --- | --- | --- |
| Deleted | Left, in card | None | List error, Refreshing | Closest filters-only match |
| Import history | None | None | List error, Refreshing | Closest empty-chrome match |
| Duplicates | Left, in card | None | List error, Refreshing | Org-scope note is already **above** the card |
| Audit | Left, in card | None | Lookup error in `toolbar` | Banner in the action slot |
| Users | None | None | Action error in `toolbar` | Banner in the action slot |
| Tickets | None | None | Pending / error banners in `toolbar` | Banner in the action slot |
| Feedback / API keys / Categories / Labels | Empty filter bar | Create in `trailing` (same row) | API keys also put the created-key banner in `toolbar` | Fake filter row |
| Activities / Locations / Pricing / Schedules | Search + Create on **one row** | Create is `trailing` | List error, Refreshing | Create is not its own row |
| Suggestions | Left, plus `summary` under the bar | None | Summary line | Copy in the filter slot |
| Category checks | Left, plus `summary` | Sweep / bulk **left** in `toolbar`; `size='sm'` | Summary line | Actions not right-aligned |
| Names / Locations (data quality) | Left, in card | Sweep / bulk **left**; summary `<p>` above the buttons | List error, Refreshing | Copy in the action slot |
| Catalog table | **Outside** the card, after the Table / Map switcher | Create + Clear import on that outside filter row; Approve / Reject / Reopen / Apply properties **left** in `toolbar` plus a checkbox | List error, Refreshing | Biggest layout split |

Shared extras on every `AdminRecordTable`: visible list-error banner,
visible “Refreshing…”, unused `footer` slot. Filter `trailing` puts
Create on the filter row (`order-first` on phones, `ml-auto` on
desktop). `toolbar` is left-aligned.

Names, Locations (data quality), Category checks, Duplicates, Import
history, and Catalog already put some banners **above** the card.
Those stay. Lift the remaining in-card banners to the same place.

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
  organization is Table-view only (today it also shows on Map).
- Category-checks buttons drop `size='sm'` so they match Names /
  Locations.

Record the four slots in the admin CRUD skill,
`.cursor/rules/admin-web.mdc`, and
`docs/architecture/admin-web-ui.md`.

## Files

- `apps/admin_web/src/components/ui/admin-record-table.tsx`
- `apps/admin_web/src/components/ui/admin-filter-bar.tsx`
- `apps/admin_web/src/components/ui/resource-table-shell.tsx`
- Every `ResourceTableShell` call site listed above
- Catalog `review-queue-panel.tsx` (filters stay page chrome)
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
