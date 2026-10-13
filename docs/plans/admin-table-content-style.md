# Plan: One table cell content style

**Status**: Approved
**Zone**: yellow

## Goal

Every admin listing cell uses one of seven roles. A role has one
component and one treatment. After this change, no table invents a
weight, color, empty word, badge, id style, number style, or second
line.

The seven roles:

1. **Name.** The row’s identifying label. One column, the first text
   column. `AdminTableName`: `font-medium`. No `truncate`.
2. **Text.** A human-readable value. Unwrapped `text-sm` inherited
   from the table body. No `text-slate-*`, no `uppercase`, no `text-xs`.
3. **Time.** An instant. `AdminTableTime`: `formatDateTime`
   (`Oct 13, 02:36 PM`) and `text-slate-600`. Tables do not call
   `formatDate`. When the time is the row identity (Imports · History
   When), pass `emphasis` so the same component adds `font-medium`.
4. **Status.** A closed set. `StatusBadge` only. Scope, enrichment,
   verdict, review, ticket type, ticket status, suggestion status,
   API key status, audit action, user role, and the current-user
   “You” mark are this role. Tones stay on `StatusBadge`.
5. **Id.** An opaque token. `AdminTableId`: `font-mono text-xs text-slate-600`.
   Ticket id, actor, import job id, place id, source id, and API key
   prefix.
6. **Number.** A count, score, order, star count, percent, or range.
   `AdminTableNumber` with `tabular-nums`. Percents render `82%`.
   Ranges render `3–12` (en dash, no spaces). Confidence is this
   role, in its own column, formatted with `formatAdminTablePercent`
   (`0.82` → `82%`).
7. **Empty.** A null or blank value of any role. The em dash `—`.
   Not “Unknown”, “No phone”, “No manager”, “Never”, or a blank cell.
   `formatDateTime` already returns the em dash; the other components
   do too.

A cell holds one role. A list of the same role is allowed (several
role badges, several rule labels). A second fact is another column.

The only caption is `AdminDataTableCellMeta`. One caption per hidden
column, in column order, `until` matching that column’s priority,
rendering the same role component as the column. An empty caption
includes the column name (`Expires —`). A caption does not
introduce a fact that has no column. Draft cells inherit each
header’s `priority` so a phone does not show extra em-dash cells.

`IdentityProviderBadge` is the value of the Users Provider column.
It is the one icon-valued status. It does not sit in the name cell.

Column priority runs primary, then every `secondary`, then every
`tertiary`. A tertiary column does not sit before a later secondary
column.

The Operations cell is `AdminRowActions` or empty. A reason there are
no actions is `sr-only`.

Draft rows: the first cell is `AdminTableName` with the draft label.
Every other draft cell is an em dash.

Map links and language flag chips stay controls inside a text cell.
They do not recolor the value.

Null `org_id` on an API key is the text `Full access`. That null is a
stored scope, not a missing organization. A missing expiry is an em
dash, not “Never”.

## Non-goals

- Table card slots, filters, actions, or Load more
- Expanded editors, dialogs, and `formatDate` outside tables
- Header wording. Headers are already CSS-uppercased
- Adding a Changed-fields column on Audit. Those values stay in the
  editor. The caption stops showing them
- Replacing language flag chips or map icons with text
- Row operations other than the Users own-account sentence

## Proposed shape

Shared components live next to `AdminDataTableCell`. Call sites render
those components and pass no color, weight, size, `truncate`, or
`uppercase` class of their own.

`AdminDataTableCell` keeps an allowlist for layout classes (`w-*`,
`pr-0`, `whitespace-nowrap`, `text-right`, `text-center`, the empty
state’s `py-8`). Weight and color on a cell are rejected.

Record the seven roles in `.cursor/skills/admin-crud-screen/SKILL.md`,
`.cursor/rules/admin-web.mdc`, and `docs/architecture/admin-web-ui.md`.

This draft supersedes the table-cell placement in
`docs/plans/user-table-email-roles.md`: roles and the provider icon
leave the email cell and become columns. The editor half of that plan
stays (no raw attributes, Groups labeled Roles, formatted timestamps
in the detail).

### Per table

- **Tickets.** Organization is the name. Ticket id is an id. Type and
  Status stay badges. Submitted by is text. Submitted is a time.
  Drop the `text-slate-400` “Reviewed …” line and add a tertiary
  Reviewed time column. The caption repeats the hidden columns,
  including ticket id, and drops district.
- **Imports · History.** When is an emphasised time. Mode and
  Organizations are text. Add captions.
- **Catalog.** Name is the name. Split Contact into Email (text),
  Phone (text), and Manager (id). Import job is an id. Complete is a
  percent. Missing stays text, including “Ready”. Drop the phone and
  manager sublines. Add captions.
- **Pricing.** Location is the name. Amount keeps its currency label
  as text. Add captions for Activity and Type.
- **Schedules.** Location is the name. An unknown language code is
  text. No languages is an em dash. Drop the `text-xs uppercase`
  code and the `text-slate-600` wrapper. Add captions.
- **Activities.** Name is the name. Age range is a number range.
  Add a caption for the age column.
- **Categories.** Path is the name. Display order is a number.
- **Locations.** Area is the name. Address is text, with the existing
  map icons. Drop `text-slate-600` on the address.
- **Suggestions.** Requested name is the name. Enrichment is a
  badge. Activity count is a number. Add captions.
- **Category checks.** Activity is the name. Verdict is a badge.
  Confidence is a new number column; a missing confidence is an em
  dash. Add captions.
- **Feedback.** Organization is the name. Stars is a number.
  Submitted is a time, not a date. Add captions for Labels,
  Submitter, and Submitted.
- **Users.** Email is the name, without `truncate`. A missing email
  shows the username, and an em dash only when both are missing.
  Add Name (text), Provider (`IdentityProviderBadge`), and Roles
  (badges, including “You”). Created and Last login are times. The
  own-account Operations sentence becomes `sr-only`.
- **API keys.** Name is the name. Scope and Status are badges.
  Status leaves the Expires cell. Expires is a time. Prefix is a new
  id column. The caption repeats those columns.
- **Audit.** Table is the name. Actor is an id. Timestamp is a time.
  The caption repeats Action, Actor, and Timestamp.
- **Deleted.** Name is the name. Place id and Source id are ids.
  Deleted is a time. Move Source id to the end so the tertiary column
  is last. Add captions.
- **Data quality · Names.** Current is the name. Proposed, Record,
  and Rules are text. Record and rule ids render as words
  (`empty address`), through one label helper. Add captions.
- **Duplicates.** Names is the name. Score is a number. Signals use
  the same label helper. Add captions.
- **Data quality · Locations.** Record is the name. Confidence is a
  new number column. Lookup uses an em dash when the grade is
  missing. Add captions.
- **Feedback labels.** Label is the name. Order is a number. Add a
  caption for Order.

## Files

- `apps/admin_web/src/components/ui/admin-data-table.tsx` and the new
  role components beside it
- `apps/admin_web/src/components/ui/resource-table-shell.tsx` (draft
  cells)
- Every `renderCells` listed above
- `apps/admin_web/src/components/admin/cognito-users/badges.tsx`
  (provider column only; role badges stay `StatusBadge`)
- `apps/admin_web/eslint.config.js` for the cell class allowlist
- Unit tests for the seven roles and the draft em dashes
- Playwright specs whose headers, empty copy, or timestamps change
  (Users, Catalog, API keys, Feedback, Deleted, Tickets)
- `.cursor/skills/admin-crud-screen/SKILL.md`
- `.cursor/rules/admin-web.mdc`
- `docs/architecture/admin-web-ui.md`

## Invariants this change preserves

- Filter query keys, apply-on-change, and debounce
- One expanded row; Operations buttons do not toggle the row
- Deep links (`org`, `tab`, `suggestion`, `audit-log`)
- Status tones already defined on `StatusBadge`
- Flag chips, map links, and the provider icon artwork
- “Full access” for an API key with no organization
- Users still cannot modify their own account
- Audit changed fields, ticket district, and import file details stay
  available in the expanded editor

## Done when

- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Unit tests cover each role’s classes, the em dash, emphasised
  time, percent and range formatting, and draft cells
- Playwright specs match the new Users, Catalog, API key, Feedback,
  Deleted, and Tickets columns and the datetime copy
- A browser pass on those six tables confirms one badge style, em
  dashes where values are missing, and phone captions that match the
  hidden columns

## Rollback

Revert the branch.

## Open questions

None. Approved for implementation.
