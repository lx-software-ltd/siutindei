# Plan: Right-align media version control

**Status**: Implemented
**Zone**: yellow

## Goal

On Media, keep the card title on the left and put the catalog version
switcher on the right of that same title row.

## Non-goals

- Changing version history, snapshots, or save behavior
- Moving the organization-page badges or version switcher
- Changing Locations, Activities, Pricing, or Schedules action bars

## Files

- `docs/plans/media-version-control-align.md`
- `apps/admin_web/e2e/media.spec.ts`

`main` already right-aligns every card title accessory with
`ml-auto` (`admin-card-title-accessory`). This branch keeps the Media
Playwright assertion and does not add a second alignment API.

## Invariants this change preserves

- Media still uses `AdminInputCard` titled `Media` with the switcher in
  the title accessory slot
- Historical versions stay read-only; Save media stays on the bar
- Organization status badges stay next to the organization name

## Done when

- The Media version switcher sits at the trailing edge of the title row
- `npx vitest run tests/components/ui/admin-input-card.test.tsx`
- Playwright media spec still opens the version menu
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
