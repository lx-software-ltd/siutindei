# Plan: One input card style

**Status**: Draft
**Zone**: yellow

## Goal

Every page-level input card uses the same four slots and the same chrome:

1. Title — visible `Card` heading (`text-base font-semibold sm:text-lg`)
2. Content — variable body (copy, fields, lists, media grid)
3. Bar — `border-t border-slate-200 pt-4` action strip
4. Inputs — the controls in that bar

Card chrome is always `Card`: white, `border-slate-200`, `shadow-sm`,
`rounded-lg` / `sm:rounded-xl`, `p-4` / `sm:p-6`. Content may differ.
Login and dialog overlays stay out of this model. Expanded row editors
stay inside the table card. Workspace org name above a **table** card
stays the table-page pattern, not an input-card title.

Add `AdminInputCard`: required `title`, optional `description`,
`children` (content), `actions` (bar inputs). It always renders the bar
so chrome matches even when `actions` is empty. Do not invent dummy
buttons.

## Non-goals

- KPI, table, or map cards
- Login or `AdminDialog`
- Changing save / decide / import / export behavior or query params
- Moving `OrganizationWorkspaceTitle` off table workspace pages

## Deviations today

Workspace choose and Readiness already match: `Card` title +
`AdminEditorPanel` bar. Everything else misses a slot or uses different
chrome or title style.

| Surface | Title | Title style | Bar | Card chrome |
| --- | --- | --- | --- | --- |
| Workspace choose | `Choose an organization` | Card `h2` | Yes — Open catalog | Card |
| Readiness | `Readiness` | Card `h2` | Yes — Approve / Reject / Reopen | Card |
| Organization | Name + badges **outside** the card. Card untitled | `text-lg font-semibold` (no `text-base` / `sm:text-lg`) | Yes — Update / Merge / Delete | Card |
| New organization | Heading **outside** the card | Same outside `h2` | Yes | Card |
| Imports | `sr-only` only | Hidden | Yes — Upload & Import | Card |
| Exports | `sr-only` only | Hidden | Yes — Export all / selected | Card |
| Suggestion settings | None (first field label is the name) | — | Yes — Save / Test | Card |
| Media | None (org name is the workspace heading above) | — | Yes — Save media | Card |
| Access / Feedback / Suggest forms | Card title | Card `h2`, Title Case | No — submit in `pt-2` with no `border-t` | Card |
| Pending tickets | Card title | Card `h2` | None | Card |
| Manager empty (no org selected / assigned) | Card title | Card `h2` | None | Card |
| Names Rules | `Rules` | `h3 text-sm font-medium` | None — Save inline | Hand-rolled flatter box (no shadow, no `sm:p-6`) |
| Locations Model budget | `Model budget` | Same `h3` | None — Save inline | Same hand-rolled box |

Title casing also drifts: workspace / Readiness are sentence case;
Access / Feedback / Suggest use Title Case (`Request Organization
Access`, `Leave Feedback`, `Suggest a Place`).

## Proposed shape

```tsx
<AdminInputCard
  title="…"
  description="…" // optional
  actions={<>…buttons…</>}
>
  {/* content — fields, lists, media grid */}
</AdminInputCard>
```

`AdminInputCard` is `Card` + `AdminEditorPanel`. Title is required.
The bar always renders (`border-t border-slate-200 pt-4`).

Per surface:

- Organization: move the workspace name (and badges) into the card
  title slot. Keep fields as content and Update / Merge / Delete on
  the bar. New organization uses title `New organization`. Leave
  `OrganizationWorkspaceTitle` above **table** cards.
- Imports, Exports, Settings, Media: visible titles (`Imports`,
  `Exports`, `Suggestion settings`, `Media`). Media keeps the workspace
  org heading above the card (table-page pattern); the card itself is
  titled `Media`.
- Access / Feedback / Suggest: keep titles; sentence-case them; move
  Submit onto the bar via `AdminEditorPanel`.
- Rules and Model budget: switch to `AdminInputCard` with those titles
  and Save on the bar.
- Pending tickets and manager empty: keep title + content; render an
  empty bar. Do not invent a dummy button.

Record the four slots in the admin CRUD skill and
`docs/architecture/admin-web-ui.md`.

## Files

- `apps/admin_web/src/components/ui/admin-input-card.tsx` (new)
- Organization (`organizations-panel.tsx`), Readiness, workspace empty
- Imports, Exports, suggestion settings, media
- Access / feedback / suggestion forms and pending notices
- Names Rules and Locations Model budget
- Playwright specs that look for outside-the-card headings
- `.cursor/skills/admin-crud-screen/SKILL.md`
- `docs/architecture/admin-web-ui.md`

## Invariants this change preserves

- Save / decide / import / export behavior and query keys
- Org heading badges (status, review, `vN`) still show
- Media stays a drag-reorder grid inside the content slot
- Table workspace pages still show the org name above the table card

## Done when

- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Unit tests for `AdminInputCard` slots (title, bar always present)
- Playwright still finds Readiness, Choose an organization, and org
  actions

## Rollback

Revert the branch.

## Open questions

None. Empty bar when there is no action; no dummy buttons.
