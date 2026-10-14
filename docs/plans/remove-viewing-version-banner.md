# Plan: Remove the Viewing version banner

**Status**: Done
**Zone**: yellow

## Goal

Drop the amber “Viewing version … · read-only” bar and the Back to
latest control it contains. Historical editors keep a single Back to
latest button on the action bar.

## Non-goals

- Changing the version switcher or snapshot lock
- Moving Back to latest off the action bar
- Version APIs

## Files

- `docs/plans/remove-viewing-version-banner.md`
- `apps/admin_web/src/components/admin/version-history.tsx`
- `apps/admin_web/src/components/shared/locations-panel.tsx`
- `apps/admin_web/src/components/shared/activities-panel.tsx`
- `apps/admin_web/src/components/shared/pricing-panel.tsx`
- `apps/admin_web/src/components/shared/schedules-panel.tsx`
- `apps/admin_web/src/components/shared/organizations-panel.tsx`
- `apps/admin_web/src/components/admin/media-panel.tsx`
- `apps/admin_web/tests/components/admin/version-history.test.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`
- `apps/admin_web/e2e/media.spec.ts`

## Invariants this change preserves

- An earlier version still locks the editor and marks changed fields
- The action bar still shows Back to latest while historical
- Latest still shows Create / Update / Save media
- Managers still see a static version pill

## Done when

- No screen renders `Viewing version` or `VersionViewBanner`
- Organization and media specs click the one remaining Back to latest
- `npx vitest run tests/components/admin/version-history.test.tsx`
- Playwright: `organizations`, `media`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
