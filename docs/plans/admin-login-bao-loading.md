# Plan: Spinning bao on the admin session notice

**Status**: Approved
**Zone**: yellow, plus the approved red callback page

## Goal

The screens between sign-in and the dashboard show one sentence,
"Preparing your admin session…", with the Hong Kong bao picture
spinning on the left. The notice has no fill, so it takes the colour
of the page behind it. There is no "Info" heading.

## Non-goals

- `StatusBanner` colours. Info banners stay white.
- The callback error banner and `completeLogin`.
- The imports redirect ("Opening the imports section.").
- Account-home loading ("Loading your account information...").
- Slowing the bao under reduced motion. The sentence stays, and the
  picture goes still, the same way the drifting bubbles do.

## Decisions

1. The picture is `bubble-bao.webp`, copied into the admin app. A full
   turn every 2.4s, linear, using the `rotate` property.
2. `prefers-reduced-motion: reduce` sets `animation: none` on the bao.
   The status text is what tells the user the session is still loading.
3. Session loading (`AuthGate` and the dashboard's matching branch)
   and the callback exchange sit on the Small World backdrop.
4. `app/admin/loading.tsx` stays on the cream page, without the
   backdrop, so a signed-in admin navigation does not flash the login
   hero. It uses the same notice and the same sentence.
5. The callback error state stays a `StatusBanner` on the plain page.

## Files

- `apps/admin_web/public/images/small-world/bubble-bao.webp` (copy)
- `apps/admin_web/src/components/login/login-loading-notice.tsx`
- `apps/admin_web/src/app/globals.css`
- `apps/admin_web/src/components/auth-gate.tsx`
- `apps/admin_web/src/components/admin/admin-dashboard.tsx`
- `apps/admin_web/src/app/admin/loading.tsx`
- `apps/admin_web/src/app/auth/callback/page.tsx` (red, approved)
- `apps/admin_web/e2e/login.spec.ts`
- `apps/admin_web/tests/components/auth-gate.test.tsx`
- `apps/admin_web/tests/components/login-loading-notice.test.tsx`
- `apps/admin_web/tests/app/auth-callback.test.tsx`
- `apps/admin_web/tests/brand/admin-chrome.test.tsx`
- `docs/architecture/admin-web-ui.md`
- `.cursor/rules/admin-web.mdc`

## Invariants this change preserves

- `completeLogin` and the callback error banner
- `AuthGate` does not router-replace
- Info, error, saved, and pending-review banners
- Six drifting bubbles on the sign-in card
- Route loading does not use the login hero

## Done when

- `npm run lint`, `npm run typecheck`, and `npm test` in `apps/admin_web`
- `npm run test:e2e -- login.spec.ts` in `apps/admin_web`
- `python3 scripts/validate_agent_rules.py`
- Browser check of the sign-in page, the held callback notice, and the
  callback error

## Rollback

Revert the branch.

## Open questions

None. The bao spins; the steamer was declined.
