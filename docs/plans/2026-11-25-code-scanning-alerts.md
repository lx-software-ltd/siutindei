# Plan: Clear open code scanning alerts

**Status**: Done
**Zone**: red

## Goal

Clear the open Semgrep and CodeQL alerts. Managed media URLs are checked
by parsed host. The GTM id is a strict `GTM-` token before it is placed
in a script URL. The CORS origin check is exact equality. The proxy and
the operator HTTP clients keep their existing https targets and carry
the in-source Semgrep mark.

## Non-goals

- No change to where the admin SPA stores Cognito bearer tokens.
- No change to the CORS origin list or the rate-limit origin that is
  selected when the admin origin is present.
- No new API route.

## Files

- `apps/admin_web/src/components/admin/media/media-panel-utils.ts`
- `apps/admin_web/tests/lib/media-panel-utils.test.ts`
- `apps/admin_web/src/lib/auth.ts`
- `apps/public_www/public/scripts/init-gtm.js`
- `backend/infrastructure/lib/api-stack.ts`
- `backend/src/app/services/aws_proxy.py`
- `scripts/cloudflare/edge_policy.py`
- `scripts/cloudflare/staging_worker.py`
- `scripts/deploy/indexnow.py`

## Invariants this change preserves

A failed IndexNow submit still returns false and still does not raise.
The HTTP proxy still rejects URLs outside the allow-list and still
rejects schemes other than http and https. Token storage is unchanged.

## Done when

`npm test` in `apps/admin_web` passes the new media URL cases.
`python3 -m pytest tests/test_public_www_indexnow.py` passes.

## Rollback

Restore the substring host check, the GTM prefix check, and the
`includes` origin check, and remove the Semgrep comments.

## Open questions

None.
