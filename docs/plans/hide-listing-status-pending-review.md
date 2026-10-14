# Plan: Hide listing status in the title while pending review

**Status**: Done
**Zone**: yellow

## Goal

The organization title shows the listing-status chip (`operational`,
`closed temporarily`, and the other listing values) only after review
is no longer `pending_review`. The review chip stays next to the name
in every review state.

## Non-goals

- Changing listing status options or how review is decided
- Changing the Details Listing status field
- Changing Readiness or Catalog review chips

## Files

- `docs/plans/hide-listing-status-pending-review.md`
- `apps/admin_web/src/components/admin/organization-workspace-title.tsx`
- `apps/admin_web/tests/components/admin/organization-workspace-title.test.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`
- `apps/admin_web/e2e/fixtures/test-fixtures.ts`
- `.cursor/skills/admin-crud-screen/SKILL.md`

## Invariants this change preserves

- Review status still appears next to the organization name
- The version tag still appears on workspace pages (`version='org'`)
- A new organization still has no badges
- Approved and rejected organizations still show listing status
- Missing `review_status` still defaults to pending review

## Done when

- Pending review: title shows the review chip and not listing status
- Approved or rejected: title shows both chips
- Vitest `organization-workspace-title.test.tsx`
- Playwright `e2e/organizations.spec.ts`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
