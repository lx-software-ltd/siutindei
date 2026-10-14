# Plan: Remove organization listing-status review hint

**Status**: Accepted
**Zone**: yellow

## Goal

The organization editor no longer shows the hint
**Review state is changed from Readiness below. Current review: …**
under Listing status.

## Non-goals

- Changing listing status options or how review state is decided.
- Changing the Readiness card or review banners.

## Files

- `apps/admin_web/src/components/shared/organizations-panel.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`

## Invariants this change preserves

- Listing status remains editable on an existing organization.
- Review state still lives on Readiness. This change is copy only.

## Done when

- Opening an existing organization shows Listing status with no
  “Review state is changed” hint.
- Playwright `organizations.spec.ts` asserts the hint is absent.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.

## Rollback

Revert the pull request.

## Open questions

None.
