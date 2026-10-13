# Plan: Remove table-card style leftovers

**Status**: Approved
**Zone**: yellow

## Goal

Every page-level table card matches the four-slot rule with the same
controls. After this change there are no extra wrappers in the filter
slot, no non-buttons on the actions row, no custom filter widths, and
no one-off button or placeholder styles.

Target, unchanged:

1. Filters — optional. Left-aligned. `AdminFilterBar` +
   `AdminFilterField` only.
2. Actions — optional new row. Left-aligned. Buttons only: create,
   sweep, bulk, and the Catalog release toggle.
3. Table.
4. Load more — optional. Outline.

Scope notes, count lines, and banners stay **above** the card.

## Non-goals

- KPI, map, or input cards
- Changing list / query / create / sweep / bulk behaviour
- Row operations
- Moving Catalog filters back out of the card
- Restyling expanded editors

## Proposed shape

### Catalog

- Drop the `space-y-2` wrapper. `filters` is a bare `AdminFilterBar`.
- When `job` is set, put a scope note **above** the Table / Map
  cards, same pattern as Names / Locations (data quality) /
  Duplicates:

  `Filtered to this import.` + underline **Show all** (clears
  `job`).

  The note is page chrome, so Map can clear the import too. Remove
  the in-card Clear import button. Drop the “Clear import is the
  Catalog exception” line from the skill and docs.
- Replace the native **Release even when details are missing**
  checkbox with a `Button` (`variant='secondary'`,
  `aria-pressed={force}`) after **Apply properties**. Pressed uses
  `variant='primary'` so on/off is visible. It stays an action, not
  a filter.

### Create button

- `AdminCreateButton` uses the same size as `Button` `md`: `h-9`,
  `w-auto`, `px-4`. Drop `h-10` and `w-full` on phones.
- Keep the component (label, `aria-pressed`, test id). It is still
  the create control. It just no longer sits taller or wider than
  Approve / Sweep on a mixed actions row.

### Category checks

- **Apply matching** and **Dismiss matching** use
  `variant='secondary'`, same as Names and Locations (data quality).
- Drop the read-only Organization `AdminFilterField`. When
  `organization` is set, show the same above-card note as Names:
  `Filtered to the organization from the review queue.` +
  underline **Show all**.

### Audit

- Delete `filterFieldClass`. Audit fields use the default
  `AdminFilterField` width (`min-w-[10rem]` / `sm:basis-48`).

### Workspace search

- Placeholders become nouns, no “Search …” and no trailing
  ellipsis:
  - Activities → `Activity`
  - Locations → `Location`
  - Pricing → `Pricing`
  - Schedules → `Schedule`
- `aria-label` matches the placeholder.

## Files

- `apps/admin_web/src/components/ui/admin-create-button.tsx`
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
- `apps/admin_web/src/components/admin/category-suggestions/category-checks-panel.tsx`
- `apps/admin_web/src/components/admin/audit-logs-panel.tsx`
- `apps/admin_web/src/components/shared/{activities,locations,pricing,schedules}-panel.tsx`
- `apps/admin_web/e2e/table-card.spec.ts` and unit tests
- CRUD skill, `admin-web.mdc`, `docs/architecture/admin-web-ui.md`

## Invariants this change preserves

- Four slots, actions left, Catalog filters inside the table card
- Catalog Table / Map still share filter state
- `job` and `organization` still scope the lists
- Force-release still only applies to Approve
- Create still opens a draft row or the Catalog workspace
- Sweep / bulk / Load more behaviour and query keys

## Done when

- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Unit: `AdminCreateButton` is `h-9` / not `w-full`; Audit fields
  have no width override
- Playwright Catalog: no Clear import inside the card; when `job`
  is set the Show all note sits outside the card; release is a
  button after Apply properties; Create and Approve heights match
- Playwright Category checks: Apply matching / Dismiss matching
  present; scoped org uses the above-card note
- Playwright workspace: Activity placeholder is `Activity`, not
  `Search activities...`

## Rollback

Revert the branch.

## Open questions

None.
