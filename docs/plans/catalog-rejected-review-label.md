# Plan: Catalog rejected review label

**Status**: Implemented
**Zone**: yellow

## Goal

On the Catalog table, the Review column shows **Rejected** for a
rejected organization. It does not append the reject reason.

## Non-goals

- Removing the reason from the organization readiness card.
- Removing the Catalog "Reject reason" filter.
- Changing stored `review_reason` values or the reject form.

## Files

- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
- `apps/admin_web/e2e/org-review.spec.ts`

## Invariants this change preserves

- The Review filter still sends `review_status=rejected`.
- The "Reject reason" filter still narrows the list.
- Pending and Approved badges stay **Pending** and **Approved**.
- Readiness still shows the reason as a read-only value.

## Done when

- Playwright asserts the Review cell says **Rejected** for an
  organization rejected as not relevant.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.

## Rollback

Revert the commit.

## Open questions

None.
