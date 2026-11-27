# Plan: Organization contact action links

**Status**: Done
**Zone**: yellow

## Goal

On the admin Organization details card, put a link under each primary
contact field:

- Email: Send a new email (`mailto:`)
- Website: Open the website (http or https, new tab)
- Phone number: Start a new chat (whatsapp) (`https://wa.me/`, new tab)

The manager organization form does not show these links.

## Non-goals

- Changing stored email, website, or phone values
- Linking the social WhatsApp handle, source URL, or public website
- A mail composer inside the admin app

## Files

- `docs/plans/org-contact-action-links.md`
- `apps/admin_web/src/components/shared/organizations/organization-contact-links.tsx`
- `apps/admin_web/src/components/shared/organizations-panel.tsx`
- `apps/admin_web/tests/components/shared/organization-contact-links.test.tsx`
- `apps/admin_web/e2e/organizations.spec.ts`
- `apps/admin_web/e2e/manager-dashboard.spec.ts`

## Invariants this change preserves

- Create, Update, Merge, and Delete stay on the Details card bar
- Manager mode still edits the same contact fields without these links
- A blank or unsafe value does not render a link
- Website and WhatsApp links open in a new tab so an open draft stays put

## Done when

- Admin org with email, website, and a possible phone shows the three
  links under those fields, with `mailto:`, the site URL, and `wa.me`
- A new organization with empty fields shows no contact links
- Manager organization form shows none of the three links
- `npx vitest run tests/components/shared/organization-contact-links.test.tsx`
- Playwright: the new cases in `e2e/organizations.spec.ts` and
  `e2e/manager-dashboard.spec.ts`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`

## Rollback

Revert the admin-web commit. No API or schema change.

## Open questions

None.
