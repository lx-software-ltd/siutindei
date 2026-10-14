# Plan: Catalog pending review label

**Status**: Accepted
**Zone**: yellow

## Goal

On the Catalog table, show **Pending** instead of **Pending review**
in the Review filter dropdown and in the Review column badge.

## Non-goals

- Changing the KPI card **Pending review**.
- Changing organization workspace badges, status banners, or other
  screens that still say pending review.
- Changing the stored `pending_review` API value.

## Files

- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`
- `apps/admin_web/e2e/table-cell-captions.spec.ts`

## Invariants this change preserves

- The Review filter still sends `review_status=pending_review`.
- Approved and Rejected filter and badge labels stay the same.
- The Catalog KPI cards keep their current copy.

## Done when

- Playwright asserts the Review filter option and column badge say
  **Pending**, not **Pending review**.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.

## Rollback

Revert the commit.

## Open questions

None.
