# Plan: Brand the admin login page as Siu Tin Dei

**Status**: Approved
**Zone**: yellow

## Goal

A signed-out visitor on the admin root recognises the public website
(stacked logo, golden Small World backdrop, chocolate ink, brand type)
and sees that this is the Siu Tin Dei admin entrance. Google, Apple, and
passwordless email sign-in stay as they are.

## Non-goals

- Restyling the signed-in console. It stays slate.
- `apps/admin_web/src/app/auth/**` (red). The callback page is a follow-up.
- Sharing assets through `shared/**`.
- Adding the licensed Aero BC webfont.
- An environment label on the login pill.
- Random bubble selection.

## Decisions

1. `viewport.themeColor` is `#f5c51b` for the whole admin app.
2. The pill reads "Admin console".
3. `LegalLinks` keeps `hover:text-slate-900`.
4. Six fixed bubbles: junk, tram, clock tower, bauhinia, lantern, teacup.
5. No staging or environment label.
6. Focus rings on the sign-in card use `brand-700` (about 7.7:1 on
   white). `brand-600` is about 2.1:1 and is not used for focus.
7. The heading keeps "Siu Tin Dei" on one line (`whitespace-nowrap`).
   `text-balance` was splitting the name.
8. The footer inner width is `max-w-3xl`. `max-w-md` wrapped
   "Terms of Use" on a desktop window.
9. Reduced motion sets `animation: none` on the pictures. The
   Playwright headless shell can still report an empty animation-name;
   the test treats that as still and rejects a named drift animation.
10. `Input` and `Label` stay on string concatenation. Login fields are
    separate elements so the console slate styles are unchanged.
11. The imports redirect and the dashboard's own loading branch use the
    same backdrop as the sign-in gate.

## Files

- `apps/admin_web/public/images/brand/siutindei-logo-stacked.svg` (copy)
- `apps/admin_web/public/images/small-world/bubble-*.webp` (six copies)
- `apps/admin_web/src/app/globals.css` (brand tokens and login backdrop)
- `apps/admin_web/src/app/layout.tsx` (`themeColor`)
- `apps/admin_web/src/components/ui/card.tsx` (`twMerge`), `button.tsx`
  (`brand` variant). `input.tsx` and `label.tsx` stay as they were.
- `apps/admin_web/src/lib/config.ts` (`getPublicWwwUrl`)
- `apps/admin_web/src/components/login/login-backdrop.tsx`
- `apps/admin_web/src/components/login/login-brand-header.tsx`
- `apps/admin_web/src/components/login/login-footer.tsx`
- `apps/admin_web/src/components/login-screen.tsx`
- `apps/admin_web/src/components/auth-gate.tsx` (loading state)
- `apps/admin_web/e2e/login.spec.ts`, `apps/admin_web/e2e/admin-dashboard.spec.ts`
- `apps/admin_web/tests/components/login-screen.test.tsx`
- `apps/admin_web/tests/components/ui/card.test.tsx`
- `docs/architecture/admin-web-ui.md`
- `.cursor/rules/admin-web.mdc`

## Invariants this change preserves

- Provider login, passwordless send and verify, config-error disabling
- Auth copy the e2e suite already asserts, except the heading
- `AuthGate` does not router-replace
- Signed-in console chrome
- Static export, same-origin assets only

## Done when

- `npm run lint`, `npm run typecheck`, and `npm test` in `apps/admin_web`
- `npm run test:e2e -- login.spec.ts admin-dashboard.spec.ts`
- `npm run build` in `apps/admin_web`
- `python3 scripts/validate_agent_rules.py`

## Rollback

Revert the branch.

## Open questions

Resolved above. No environment label.
