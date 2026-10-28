# Plan: Tighten admin login copy

**Status**: Draft
**Zone**: yellow

## Goal

The signed-out admin login page drops the "Sign in to Siu Tin Dei
Admin" heading. Social buttons read "Sign in with Google" and
"Sign in with Apple". The email field label reads "Sign in with your
email". Logo, Admin console pill, subtitle, and sign-in behaviour stay.

## Non-goals

- `apps/admin_web/src/app/auth/**` (red)
- Changing passwordless, Google, or Apple behaviour
- Restyling the signed-in console
- Changing the mobile app login copy

## Files

- `apps/admin_web/src/components/login-screen.tsx`
- `apps/admin_web/tests/components/login-screen.test.tsx`
- `apps/admin_web/e2e/login.spec.ts`
- `docs/architecture/admin-web-ui.md`

## Invariants this change preserves

- Provider login, passwordless send and verify, config-error disabling
- Logo, Admin console pill, subtitle, and legal footer
- `LoginBrandHeader` still accepts an optional title for other surfaces

## Done when

- `npm test -- tests/components/login-screen.test.tsx` in `apps/admin_web`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Browser check of the signed-out login page
- `npm run test:e2e -- e2e/login.spec.ts` when Playwright is available

## Rollback

Revert the branch.

## Open questions

None.
