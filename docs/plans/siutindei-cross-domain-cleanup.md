# Plan: Remove the remaining lx-software.com coupling from siutindei

**Status**: Draft
**Zone**: red (`backend/infrastructure/**`, Cloudflare live config, SES).
Each step below waits for explicit approval before it is written.

Follows `siutindei-domain-consolidation.md`. Every siutindei service
hostname now lives on `siutindei.com`. The audit of 2026-11-09 found four
remaining kinds of cross-domain coupling. The lx-software board API URL is
fixed separately and is out of scope here.

| # | Area | Today | Target |
|---|---|---|---|
| A | Outbound email | `hello@`, `no-reply@`, `support@lx-software.com` | `@siutindei.com` |
| B | Board inbound copy | Email Worker forwards to `siutindei-board@inbound.lx-software.com` | `siutindei-board@inbound.siutindei.com` |
| C | Dead names in config | CORS defaults and Worker `siutindei-canonical-redirects` list `siutindei.lx-software.com` / `siutindei-www.lx-software.com` | removed |
| D | Identifiers | stack names, Cognito prefix, Apple Services ID and app ID all start `lxsoftware` / `com.lxsoftware` | decide per item (below) |
| E | Raw API host | `0q7ttmw461.execute-api…/prod` answers like `api.siutindei.com` | disabled |

## Goal

No siutindei traffic, address or public configuration depends on
`lx-software.com`. The raw `execute-api` host is closed, so
`api.siutindei.com` is the only way into the REST API.

## Non-goals

- The lx-software board API base URL (fixed separately).
- Renaming CloudFormation stacks, the Aurora cluster, or S3 buckets (see D).
- Changing the legal entity. "LX Software" stays the data controller in
  the privacy policy; only the contact address changes.
- Evolvesprouts (tracked in the consolidation plan, track E).

## A. Outbound email to `@siutindei.com`

Facts:

- The SES domain identity `siutindei.com` exists and is verified (DKIM
  CNAMEs `ryojt…`, `d6hy…`, `wmp6…`, and MAIL FROM `mail.siutindei.com` are
  in the zone). The lx-software stack owns it
  (`SiutindeiBoardMailSendingIdentity`, `SiutindeiBoardMailSendingEnabled=true`).
- Siutindei grants `ses:SendEmail` / `SendRawEmail` on
  `identity/<address>` for `AuthEmailFromAddress` (auth challenge Lambda)
  and `SesSenderEmail` (admin and manager-request Lambdas). When only the
  domain is verified, SES authorises against `identity/siutindei.com`. So
  changing the parameters alone gives `AccessDenied`.
- Inbound `@siutindei.com` already works: Cloudflare Email Routing sends
  every address (catch-all and `hello@`) to Worker `siutindei-mail-fanout`,
  which forwards to the owner's inbox.

Steps:

1. Infra (red). In `api-stack.ts`, add `identity/siutindei.com`, derived
   from the sender's domain, to the three SES policies next to the address
   ARN. Deploy with the current `lx-software.com` values, so nothing changes
   yet.
2. Params (red). `AuthEmailFromAddress=hello@siutindei.com`,
   `SesSenderEmail=no-reply@siutindei.com`,
   `SupportEmail=support@siutindei.com`, and
   `OpsAlertsEmail=support@siutindei.com`. The SNS email subscription is
   replaced, and the owner clicks one confirmation mail.
3. Content (green). Change the `support@lx-software.com` contact in
   `apps/public_www/src/content/legal/{en,zh-HK}.json`,
   `apps/public_www/tests/lib/legal-content.test.ts`,
   `docs/legal/README.md`, `docs/legal/store-disclosures.md`, and the SES
   section of `docs/deployment/launch-checklist.md`.
4. Owner, outside the repo: update the privacy contact in App Store Connect
   and Play Console.

Prerequisite: the lx-software stack must keep the `siutindei.com` identity.
Record that dependency in both repos' docs, because deleting it there would
stop siutindei mail.

## B. Board inbound copy on `inbound.siutindei.com`

This plumbing is invisible to senders: mail to `hello@siutindei.com` is
copied by the Worker to an lx-software SES address. Moving it needs the
lx-software repo, which the agent cannot push.

1. Cloudflare (agent): `MX inbound.siutindei.com 10
   inbound-smtp.ap-southeast-1.amazonaws.com`, plus `_dmarc.inbound` TXT,
   mirroring `inbound.lx-software.com`. The verified `siutindei.com`
   identity covers receiving for the subdomain.
2. lx-software repo (owner merges): add a receipt rule on the active rule
   set `lxsoftware-inbound-mail` for `siutindei-board@inbound.siutindei.com`.
   It writes to the same bucket and prefix (`inbound-raw/siutindei/`).
   Point `SiutindeiBoardMailInboundAddress` at it. Keep the old rule until
   step 4 is done.
3. Cloudflare dashboard (owner): Email Routing → Destination addresses →
   add the new address. The verification mail lands in the bucket; open it
   and click the link.
4. Worker `siutindei-mail-fanout`: set `BOARD_DESTINATION` to the new
   address. Send a test to `hello@siutindei.com` and confirm one object
   under `inbound-raw/siutindei/` with `X-Original-To`. Then remove the old
   receipt rule and destination.

## C. Dead names in config

1. Remove `https://siutindei.lx-software.com` from the CORS defaults in
   `api-stack.ts` and `backend/src/app/utils/responses.py`, and from
   `docs/architecture/{security,aws-assets-map}.md` and
   `docs/deployment/admin-web.md`. Switch
   `tests/test_search_handler.py::_event` to `https://admin.siutindei.com`,
   and add a test that the old origin is not echoed.
2. Worker `siutindei-canonical-redirects`: drop
   `siutindei-www.lx-software.com` from `REDIRECT_HOSTS`. The source is only
   live today; commit it under `scripts/cloudflare/workers/` with a
   `node --test` case, so the next change is reviewed.
3. Rewrite the `*.siutindei.lx-software.com` examples in
   `docs/architecture/cloudflare-optimization.md` to the real hosts.

## D. Identifiers

| Identifier | Visible to | Cost to change | Recommendation |
|---|---|---|---|
| Stack names `lxsoftware-siutindei*`, Aurora `lxsoftware-siutindei-db-cluster`, buckets `lxsoftware-siutindei-*` | AWS console only | New stacks mean a new database, user pool and buckets, plus a data migration | Keep |
| Cognito prefix `lxsoftware-siutindei-prod` | Nobody while `auth.siutindei.com` exists; `RemoveCognitoAuthDomain` deletes it | Params change; only matters for rollback | Keep |
| Apple Services ID `com.lxsoftware.siutindei.auth` | Not shown to users | New Services ID, key association, Cognito IdP update and a login window | Keep |
| App ID `com.lxsoftware.siutindei` (Android `applicationId`, iOS bundle ID, URL scheme `com.lxsoftware.siutindei://`) | Store listing URLs | Free now; permanent after the first store release | Decide before first release (open question) |

## E. Close the raw `execute-api` host

Mirror the evolvesprouts patch, because API Gateway only applies the flag
on a stage update.

1. Infra (red), with tests first in `assert-existing-db.ts`:
   - Parameter `ApiDisableExecuteApiEndpoint` (default `false`).
   - Condition `DisableExecuteApiEndpoint`, true when the parameter is
     `true` and `UseApiSecondaryCustomDomain` holds.
   - RestApi `DisableExecuteApiEndpoint` override.
   - Stage variable `executeApiEndpoint` that flips with the condition.
   - `production.json` gets the parameter as `"false"`. Deploy.
2. Consumers to confirm before flipping:
   - Admin web `NEXT_PUBLIC_API_BASE_URL=https://api.siutindei.com` (done).
   - Public website search origin `api.siutindei.com` (done).
   - The lx-software board (fixed separately).
   - The mobile build uses `ApiSecondaryCustomDomainUrl`, so drop the
     `ApiUrl` fallback in `build_amplify_config.py`, or make it fail when no
     custom domain is present.
   - No webhooks are registered against the raw host; the repo has no
     inbound webhook routes.
3. Set `ApiDisableExecuteApiEndpoint=true` and deploy.

Check: `https://0q7ttmw461.execute-api.ap-southeast-1.amazonaws.com/prod/v1/activities/search`
returns `403`, and `https://api.siutindei.com/v1/activities/search` still
returns `401` without credentials. Admin sign-in and a website search both
work.

## Files

- `backend/infrastructure/lib/api-stack.ts` (A1, C1, E1)
- `backend/infrastructure/params/production.json` (A2, E1, E3)
- `backend/infrastructure/scripts/assert-existing-db.ts` (E1)
- `backend/src/app/utils/responses.py`, `tests/test_search_handler.py` (C1)
- `scripts/deploy/build_amplify_config.py`, `tests/test_build_amplify_config.py` (E2)
- `scripts/cloudflare/workers/siutindei-canonical-redirects.js` and test (C2, new)
- `apps/public_www/src/content/legal/*.json`, `apps/public_www/tests/lib/legal-content.test.ts` (A3)
- Docs: `docs/legal/*`, `docs/deployment/{launch-checklist,admin-web}.md`,
  `docs/architecture/{security,aws-assets-map,cloudflare-optimization}.md`
- lx-software repo: receipt rule and output (B2), and an SES identity
  dependency note (A)

## Invariants this change preserves

- Passwordless sign-in mail, manager-request mail and ops alerts keep
  sending at every step. The IAM grant is widened before the From address
  changes.
- Every `@siutindei.com` message still reaches the owner's inbox. The board
  copy has a single destination at any moment.
- `api.siutindei.com` behaviour, WAF and authorizers are unchanged.
- No secret, IP address or personal email address enters the repo.

## Done when

- `pytest tests backend`, `npm run test:infra`, the public website tests and
  `pre-commit` pass.
- A passwordless sign-in email arrives from `hello@siutindei.com`. An ops
  alert test (`aws cloudwatch set-alarm-state … ALARM`) reaches
  `support@siutindei.com`.
- A test mail to `hello@siutindei.com` reaches the owner, and the board
  copy lands under `inbound-raw/siutindei/` via `inbound.siutindei.com`.
- `rg "lx-software\.com"` across siutindei code and config returns only
  `www.lx-software.com` (the company link on the holding page) and legal
  entity wording.
- The raw `execute-api` URL returns `403`.

## Rollback

- A: revert the params. The widened IAM grant is harmless and can stay.
- B: set `BOARD_DESTINATION` back. The old receipt rule stays until B4.
- C: redeploy the previous Worker source. CORS changes are a code revert.
- E: `ApiDisableExecuteApiEndpoint=false` and deploy.

## Open questions

- App ID: rename `com.lxsoftware.siutindei` before the first store release
  (for example to `com.siutindei.app`, which the lx-software board fixtures
  already assume), or keep it? After the first release it is permanent.
- Sender split: is `no-reply@` right for manager-request notices, or should
  they come from `hello@` so replies reach the inbox?
- Should the support contact in the legal pages be `support@` or `hello@`
  (the address Email Routing already has its own rule for)?
