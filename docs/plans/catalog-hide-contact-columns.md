# Plan: Hide catalog contact columns

**Status**: Accepted
**Zone**: yellow

## Goal

Remove Email, Phone, and Manager from the Catalog table (desktop
columns and the phone captions under the name). Contact stays on the
organization editor and in Apply properties.

## Non-goals

- Changing the Sort dropdown (Name / Recently imported).
- Removing email, phone, or manager from the organization form or
  bulk-property dialog.
- Changing the org-review API payload.

## Files

- `docs/plans/catalog-hide-contact-columns.md`
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`
- `apps/admin_web/e2e/table-cell-captions.spec.ts`
- `apps/admin_web/e2e/org-review.spec.ts`

## Invariants this change preserves

- Catalog still lists Name, Source, Review, Import job, Missing, and
  Complete.
- Phone captions still repeat the remaining hidden columns under the
  name (Source, Review, then tertiary columns).
- Sort stays a filter: default Name (A–Z, then id). Recently imported
  sends `sort=last_imported_at` (newest `last_imported_at`, nulls
  last, then newest id).
- Apply properties still edits email, phone, and manager_id.

## Done when

- Playwright catalog specs assert Email, Phone, and Manager are gone
  from the table, and Sort sends `sort=last_imported_at`.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- Playwright `organizations.spec.ts`, `org-review.spec.ts`, and
  `table-cell-captions.spec.ts` pass.

## Rollback

Revert the pull request.

## Open questions

None. The Sort control is already labeled Sort for assistive tech.
Name is alphabetical. Recently imported is newest import time first.
