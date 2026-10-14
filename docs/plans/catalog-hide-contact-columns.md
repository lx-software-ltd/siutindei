# Plan: Hide catalog contact columns

**Status**: Accepted
**Zone**: yellow

## Goal

Remove Email, Phone, and Manager from the Catalog table (desktop
columns and the phone captions under the name). Contact stays on the
organization editor and in Apply properties.

Rename the Catalog name filter placeholder to “Organization name”
and the sort option labels to “Sort by name” / “Sort by recently
imported”. API sort values stay `name` and `last_imported_at`.

## Non-goals

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
- Sort stays a control: default “Sort by name” (A–Z, then id).
  “Sort by recently imported” sends `sort=last_imported_at` (newest
  `last_imported_at`, nulls last, then newest id).
- Apply properties still edits email, phone, and manager_id.

## Done when

- Playwright catalog specs assert Email, Phone, and Manager are gone
  from the table, the name placeholder is “Organization name”, and
  Sort sends `sort=last_imported_at` when “Sort by recently imported”
  is selected.
- `npm run lint` and `npm run typecheck` pass in `apps/admin_web`.
- Playwright `organizations.spec.ts`, `org-review.spec.ts`, and
  `table-cell-captions.spec.ts` pass.

## Rollback

Revert the pull request.

## Open questions

None. The Sort control is labeled Sort for assistive tech. The
visible options are “Sort by name” and “Sort by recently imported”.
