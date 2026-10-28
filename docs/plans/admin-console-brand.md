# Plan: Align the admin console chrome with the public site

**Status**: Accepted
**Zone**: yellow

## Goal

Make the signed-in admin console recognisable as Siu Tin Dei without
redesigning the workspace. The frame uses the public Small World
palette. Tables stay dense and neutral.

## Non-goals

- No new screens, layout, or type scale.
- No Aero BC webfont and no environment label.
- No recolor of page-level copy outside the shared primitives.
- Table row hover, expanded, and draft colours stay as they are.
- Status colours other than the neutral badge and the info banner stay
  semantic. `src/app/auth/**` stays untouched.

## Decisions

1. Canvas is `bg-brand-50`. Cards stay white.
2. Primary buttons are yellow (`accent-500`, ink text). Pressed
   icon buttons and count badges use `ink-900`.
3. The active nav item is `bg-ink-900 text-white`.
4. The header keeps `/images/siutindei-logo.svg` at 64px.
5. Colour changes stop at the shared primitives and the body. Page
   files are not swept.
6. Login fields go back to `Input` and `Label` once those defaults
   are on-brand. `twMerge` lets an error border replace the default.
7. The console footer links to the public site.
8. No environment label.

## Files

- `apps/admin_web/src/app/globals.css`
- `apps/admin_web/src/components/ui/*` primitives listed in the
  implementation (button, fields, card, table, dialog, tabs, banner)
- `apps/admin_web/src/components/app-shell.tsx`
- `apps/admin_web/src/components/legal-links.tsx`
- `apps/admin_web/src/components/login-screen.tsx`
- `apps/admin_web/src/app/admin/loading.tsx`
- `apps/admin_web/src/app/error.tsx`
- `apps/admin_web/public/favicon.ico` and `favicon.svg`
- `docs/architecture/admin-web-ui.md`
- `.cursor/rules/admin-web.mdc`

## Invariants this change preserves

- Page names, table slots, and button sizes stay the same.
- Draft rows stay amber. Expanded and hover rows stay slate.
- Danger and success actions stay red and emerald.
- Provider login and passwordless email stay the same.
- The header title stays "Siu Tin Dei Admin".

## Done when

- `npm test`, `npm run lint`, and `npm run typecheck` in `apps/admin_web`.
- `npx playwright test e2e/login.spec.ts e2e/admin-dashboard.spec.ts e2e/feedback.spec.ts e2e/table-card.spec.ts`.
- The theme test shows the public colour and font tokens match.
- A browser pass of Catalog at desktop width and the login page.

## Rollback

Revert the branch.

## Open questions

Resolved by the defaults above.

## Corrections

These replace the earlier choices where a review showed they collide.

1. The neutral badge stays grey (`bg-slate-200 text-slate-700`). A cream chip reads as pending.
2. Info banners are white with a `brand-200` border, so they sit on the cream page. `pending-review` stays blue.
3. `app/admin/loading.tsx` is a spinner on the cream page. The login page, session loading, and the imports redirect keep the golden backdrop.
4. `Input`, `Select`, and `Textarea` keep `twMerge`, so `formErrorClassName` replaces the field border. `Label` does not merge, so its `mb-1` stays.
5. Focus rings opt in through `.admin-focus` on the shell, the login backdrop, and portaled menus. The transition list includes transform and leaves outline colour out, so the ring does not fade and a moving control still moves. Rings inside a scrolling table are inset.
6. Primary stays yellow. A disabled primary is grey. `secondary` is filled `bg-brand-100`. `outline` stays white. `ConfirmDialog` confirms with `ink`.
7. Tab tracks are white with a gold border. The active language flag uses an ink ring.
8. `PublicSiteLink` is the one public-site link. It opens in a new tab from the login footer and the console footer.
9. Leftover cool copy, borders, and menus use ink and brand surfaces. Row hover, expanded rows, and draft rows stay neutral. The expanded-row frame stays `slate-300`.
10. The header title is "Siu Tin Dei". The pill still says "Admin console".
11. `--font-sans` in both apps includes the emoji faces from Tailwind's default stack.
12. Legal-link hover is `brand-700`.
13. The theme test matches colour and font tokens in both directions, and the admin favicons match the public site byte for byte.
14. This branch stays stacked on the login branch. Merge that pull request first. A squash there means this pull request needs its base brought up to date before it can merge.
