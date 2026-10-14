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
- `apps/admin_web/src/components/ui/card.tsx`
- `apps/admin_web/src/components/ui/admin-input-card.tsx`
- `apps/admin_web/src/components/admin/media-panel.tsx`
- `apps/admin_web/tests/components/ui/admin-input-card.test.tsx`
- `apps/admin_web/e2e/media.spec.ts`

## Invariants this change preserves

- Media still uses `AdminInputCard` titled `Media` with the switcher in
  the title accessory slot
- Historical versions stay read-only; Save media stays on the bar
- Organization status badges stay next to the organization name

## Done when

- The Media title row is `justify-between` so the switcher sits at the
  trailing edge
- `npx vitest run tests/components/ui/admin-input-card.test.tsx`
- Playwright media spec still opens the version menu
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
