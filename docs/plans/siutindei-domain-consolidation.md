# Plan: move admin, API, and Cognito onto siutindei.com

**Status**: Draft, awaiting approval. No infrastructure has been changed.
**Zone**: red (`backend/infrastructure/**`, `backend/src/app/utils/responses.py`
indirectly through CORS, deploy workflows). Documentation and the Cloudflare
records are green.

## Goal

Every public hostname of the product lives under `siutindei.com`:

| Surface | Today | Target |
|---|---|---|
| Admin console (CloudFront) | `siutindei.lx-software.com` | `admin.siutindei.com` |
| REST API (API Gateway custom domain) | `siutindei-api.lx-software.com` | `api.siutindei.com` |
| Cognito Hosted UI (custom domain) | `siutindei-auth.lx-software.com` | `auth.siutindei.com` |
| Public website staging (CloudFront) | `siutindei-www-staging.lx-software.com` | `www-staging.siutindei.com`, reachable only from an IP allow-list |
| Public website | `siutindei.com` | unchanged |

The target layout mirrors the `evolvesprouts.com` zone (sibling repository
`lx-software-ltd/evolvesprouts`): `admin.`, `api.`, `auth.`, and
`www-staging.` under the product domain, with staging behind the same
Cloudflare Worker pattern that redirects everyone outside an IP allow-list
to the production site. `auth` is also the subdomain Cognito's own guide
recommends.

The old `lx-software.com` hostnames keep working for a transition period:
the admin hostname 301s to the new one, and the API hostname stays mapped
to the same stage until every client has moved. Cognito cannot run two
custom domains, so it switches in one planned window.

## Non-goals

- Changing the Cloudflare edge policy for the apex (`siutindei.com`).
- Flipping the canonical public hostname from the apex to `www.` to match
  evolvesprouts. The apex is what Google has indexed; the `www` → apex
  redirect already exists and the set of hostnames is the same either way.
  Listed as an open question, not planned.
- Product-specific evolvesprouts hostnames that have no siutindei
  counterpart yet: `media.` (asset download CloudFront), `training.`,
  `inbound.` (SES inbound mail), `bounce.` (Stripe).
- Changing email senders (`hello@`, `no-reply@`, `support@lx-software.com`).
  SES DKIM and MX records for `siutindei.com` and `partners.siutindei.com`
  already exist in Cloudflare, so this is possible later as its own plan.
- Proxying the new hostnames through Cloudflare (orange cloud). They stay
  DNS-only like today; see the invariant about path-scoped rules below.
- Changing the mobile bundle ids or deep-link schemes
  (`com.lxsoftware.siutindei://…`).

## What the live audit found (2026-11-09, read-only)

Cloudflare (`CLOUDFLARE_API_TOKEN`, zone reads):

| Item | Value | Consequence |
|---|---|---|
| Zone `siutindei.com` (Free) | apex and `www` CNAME `d2zpx4ub70d0qj.cloudfront.net`, proxied; SSL `strict`; the four public-www rulesets from the edge plan are live | The zone is healthy. No `admin`, `api`, or `auth` records exist yet. |
| Edge certificate for `siutindei.com` | Google Trust Services, SANs `siutindei.com`, `*.siutindei.com` | Not needed for grey-cloud records, but covers the new names if any is ever proxied. |
| Apex resolves to A records | CNAME flattening on the proxied apex | Satisfies Cognito's "parent domain must have an A record" rule for `auth.siutindei.com`. |
| `_04e18a…siutindei.com` CNAME → `acm-validations.aws` | present | DNS validation record for the existing ACM `*.siutindei.com` certificate. A new request for the same names in another region reuses the same record. |
| Zone `lx-software.com` (Free) | `siutindei.lx-software.com` → `denj3rteq1wli.cloudfront.net` (grey); `siutindei-api` → `d-qe82upw0p5.execute-api.ap-southeast-1.amazonaws.com` (grey); `siutindei-auth` → `d30rdsgebcvmh5.cloudfront.net` (grey); `siutindei-www` → proxied, Worker `siutindei-canonical-redirects` | The three records to retire. The Worker route shows the zone already uses proxied records purely for 301s. |
| `lx-software.com` settings | SSL `full`, `always_use_https` off, min TLS 1.0 | Fine for a redirect-only hostname; not touched by this plan. |
| Rulesets on `lx-software.com` | one `http_request_dynamic_redirect` rule (apex → www) | Redirect Rules are available on Free; a second single redirect fits. |
| Token scope | zone list, DNS read, settings read, rulesets read, Workers read and script download; `certificate_packs`, IP lists, and Access denied | DNS:Edit on both zones and Workers Scripts:Edit are required before the apply steps. |
| Zone `evolvesprouts.com` (Free), the template | apex proxied with a Redirect Rule → `www`; `www` and `www-staging` proxied to CloudFront; `admin`, `auth`, `media` grey; `training` proxied; SSL `strict`, min TLS 1.2 | Same shape this plan produces for siutindei, apart from apex-vs-`www` canonical. |
| `www-staging.evolvesprouts.com` gate | Worker `evolvesprouts-www-staging-redirect-allowlist` on route `www-staging.evolvesprouts.com/*`: if `CF-Connecting-IP` is in a hard-coded allow-list, `fetch(request)`; otherwise 302 to `https://www.evolvesprouts.com` + path + query. Live probe from this VM: `302` → `https://www.evolvesprouts.com/en/`. | The pattern to copy. Its weaknesses, fixed in the siutindei version: the IP list lives only in the deployed script, and GitHub runners are not in it, so `smoke-public-www-staging.yml` follows the redirect and tests production. |
| `api.evolvesprouts.com` | proxied CNAME to `hcb6ndyt38.execute-api.ap-southeast-1.amazonaws.com`; evolvesprouts `ApiCustomDomainName` is empty; live probe returns `530` / Cloudflare error 1016 | Not a working pattern. API Gateway needs a custom domain mapped to the hostname. This plan keeps `api.siutindei.com` grey with a real API Gateway custom domain. |
| Zero Trust Access | `access.api.error.not_enabled` on the account | Confirms the Worker, not Access, is the available staging gate (the edge plan's step 8 assumed Access). |
| `siutindei-www-staging.lx-software.com` today | grey CNAME to `d2y0sgtf8djbdr.cloudfront.net`; live probe `200` with `server: AmazonS3` | Open to anyone who knows the hostname, including the staging search fixture. |

AWS (`cursor-cloud-agent` IAM user; live TLS probes where IAM denied):

| Item | Value | Consequence |
|---|---|---|
| API Gateway custom domain | `siutindei-api.lx-software.com`, REGIONAL, TLS 1.2, cert `af726e1f` (ap-southeast-1), base path mapping → REST API `0q7ttmw461` stage `prod` | The only API Gateway domain in the region. |
| Cert `af726e1f` (ap-southeast-1) | presents `*.lx-software.com`, `lx-software.com`; expires 2027-03-03 | Cannot serve `api.siutindei.com`. A new regional certificate is required. |
| Cert `ea553e5a` (us-east-1), used by admin-web and Cognito | presents `*.lx-software.com`, `lx-software.com`; expires 2027-02-28 | Cannot serve `admin.` or `auth.siutindei.com`. |
| Cert `74786db9` (us-east-1), used by public-www | presents `*.siutindei.com`, `siutindei.com`; expires 2027-03-09 | Reusable for both the admin CloudFront alias and the Cognito custom domain. |
| Cognito prefix domain `lxsoftware-siutindei-prod.auth.ap-southeast-1.amazoncognito.com` | does not resolve | The stack deleted it when the custom domain was introduced. A Cognito switch therefore has a window with no Hosted UI unless the prefix domain is recreated first. |
| REST API `0q7ttmw461` stage `prod` | regional WAF `lxsoftware-siutindei-api-waf` attached | Unchanged by a domain change. |
| IAM for `cursor-cloud-agent` | `apigateway:GET` allowed; CloudFormation, ACM, CloudFront, Cognito, SES, WAF, Route 53, Amplify all denied | The apply steps below need an operator with console or admin CLI access. Granting the agent `acm:Describe*`, `cloudfront:Get*`, `cognito-idp:Describe*`, and `cloudformation:Describe*` would let it verify later phases. |

Cognito facts the design is built on (AWS developer guide, fetched during the
audit): one custom domain per user pool; an existing custom domain must be
deleted before another is created; a prefix domain and a custom domain may
coexist; the certificate must be in `us-east-1`; the parent domain must
resolve to an A record. `AWS::Cognito::UserPoolDomain` treats `Domain` as
immutable, so a parameter change is a replacement, and CloudFormation creates
the replacement before deleting the old resource, which Cognito rejects.
The same create-before-delete ordering applies to
`AWS::ApiGateway::DomainName`.

## Design

### DNS (Cloudflare, both zones)

New records, all DNS-only (grey):

| Record | Type | Target |
|---|---|---|
| `admin.siutindei.com` | CNAME | `denj3rteq1wli.cloudfront.net` (admin-web distribution) |
| `api.siutindei.com` | CNAME | `ApiSecondaryCustomDomainTarget` stack output (a new `d-….execute-api.ap-southeast-1.amazonaws.com` value) |
| `auth.siutindei.com` | CNAME | `CognitoCustomDomainCloudFront` stack output after phase 2 (a new CloudFront hostname; the current `d30rdsgebcvmh5` belongs to the old domain and is deleted with it) |

Plus one proxied record:

| Record | Type | Target | Proxied |
|---|---|---|---|
| `www-staging.siutindei.com` | CNAME | `d2y0sgtf8djbdr.cloudfront.net` (staging distribution) | yes, so the Worker and the origin lock can act |

Transition records in `lx-software.com`:

- `siutindei.lx-software.com`: flip to proxied and add a Redirect Rule
  `http.host eq "siutindei.lx-software.com"` → 301
  `https://admin.siutindei.com${http.request.uri.path}` with query
  preserved. Same pattern the zone already uses for `siutindei-www`.
- `siutindei-api.lx-software.com`: unchanged until phase 4, then deleted.
- `siutindei-auth.lx-software.com`: deleted in phase 2 once the new
  Cognito domain answers. Cognito does not serve a redirect, and leaving a
  dangling CNAME to a deleted CloudFront distribution is a takeover risk.
- `siutindei-www-staging.lx-software.com`: deleted in phase 3. Nobody
  outside the team should have it bookmarked, and a redirect would only
  advertise the new staging hostname.

### Certificates (ACM)

- `us-east-1`: reuse `74786db9` (`siutindei.com`, `*.siutindei.com`) for
  `AdminWebCertificateArn` and `CognitoCustomDomainCertificateArn`.
- `ap-southeast-1`: request a new certificate for `*.siutindei.com` and
  `siutindei.com` with DNS validation. ACM issues the same validation CNAME
  for the same names across regions in one account, so the existing
  `_04e18a…` record should validate it without a DNS change; if the console
  shows a different CNAME, add it in Cloudflare. Its ARN becomes
  `ApiSecondaryCustomDomainCertificateArn`.

### API: run both hostnames, then retire one

`backend/infrastructure/lib/api-stack.ts` gains an optional second domain:

- Parameters `ApiSecondaryCustomDomainName` and
  `ApiSecondaryCustomDomainCertificateArn`, default empty.
- Condition `UseApiSecondaryCustomDomain` (both non-empty), a second
  `apigateway.DomainName` (REGIONAL, TLS 1.2) and `BasePathMapping` to the
  same `prod` stage, and outputs `ApiSecondaryCustomDomainTarget` and
  `ApiSecondaryCustomDomainUrl`.
- `resolveCorsAllowedOrigins()` defaults and `_DEFAULT_CORS_ORIGINS` in
  `backend/src/app/utils/responses.py` add `https://admin.siutindei.com`
  and `https://api.siutindei.com`; the old origins stay until phase 4.

Why a second resource rather than changing `ApiCustomDomainName`: a
replacement would delete `siutindei-api.lx-software.com` at the end of the
same deploy, cutting the public website's search proxy and the admin
console until their own deploys finish. With a second resource the new
hostname is live before any client moves, and the retirement is a parameter
flip. In phase 4 the parameter wiring is swapped in code so that
`ApiCustomDomainName` feeds the construct that holds `api.siutindei.com`
(parameter-to-construct wiring can change freely; logical ids cannot), and
the secondary parameters are removed. The logical id of the surviving
resource stays as created in phase 1.

Consumers that move to `https://api.siutindei.com` once it answers:

- `SearchApiProxyOriginDomain` in `params/production.json` (public-www
  CloudFront origin; in-place CloudFront update). The `X-Origin-Verify`
  secret is unchanged.
- GitHub production variable `NEXT_PUBLIC_API_BASE_URL` (admin web build).
- `scripts/ops/board-importer` default `API_BASE`.
- `scripts/deploy/build_amplify_config.py`: prefer
  `ApiSecondaryCustomDomainUrl` when present so TestFlight builds pick up
  the new host. `tests/test_build_amplify_config.py` gets the matching case.

### Cognito: two deploys inside one maintenance window

1. Before the window: add `https://auth.siutindei.com/oauth2/idpresponse`
   as an authorised redirect URI on the Google OAuth client and as a return
   URL on the Apple Services ID. Keep the old URI until phase 4. Add
   `https://admin.siutindei.com/auth/callback` and
   `https://admin.siutindei.com/` to `CognitoCallbackUrls` and
   `CognitoLogoutUrls` (plain app-client update, no replacement; can ship
   with phase 1).
2. Deploy A: `CognitoCustomDomainName=""` and
   `CognitoCustomDomainCertificateArn=""`. The `UseCognitoAuthDomain`
   condition recreates the prefix domain, and the custom domain
   `siutindei-auth.lx-software.com` is deleted. Hosted UI is now only at
   `lxsoftware-siutindei-prod.auth.ap-southeast-1.amazoncognito.com`.
3. Deploy B: `CognitoCustomDomainName=auth.siutindei.com`,
   `CognitoCustomDomainCertificateArn=<74786db9>`. The
   `RemoveCognitoAuthDomain` custom resource deletes the prefix domain,
   then `SiutindeiUserPoolCustomDomain` is created. This is the exact path
   the stack took when the custom domain was first introduced. Cognito
   provisions its CloudFront distribution in roughly 5 to 15 minutes; the
   output `CognitoCustomDomainCloudFront` is the DNS target.
4. Create `auth.siutindei.com` CNAME, delete `siutindei-auth.lx-software.com`.
5. Rebuild the admin web with `NEXT_PUBLIC_COGNITO_DOMAIN=auth.siutindei.com`.

Impact during the window: new admin sign-ins and token refresh
(`/oauth2/token`) fail; already-issued access tokens keep validating because
the authorizers use the user pool JWKS, not the custom domain. The public
website does not use Cognito. Budget about one hour.

### Admin console

- `params/production.json`: `AdminWebDomainName=admin.siutindei.com`,
  `AdminWebCertificateArn=<74786db9>`, `NominatimUserAgent` and
  `NominatimReferer` updated to the new URL.
- The CloudFront distribution updates in place (alias and certificate).
  While it propagates, `siutindei.lx-software.com` answers 403 from
  CloudFront because the alias is gone, so the Cloudflare redirect goes in
  first. Only the alias set and the certificate change; the S3 origin,
  OAI, WAF, and logging are untouched.
- Deploy `deploy-admin-web.yml` with the two new variables so the bundle
  points at `api.siutindei.com` and `auth.siutindei.com`.

### Public website staging

- `params/production.json`: `PublicWwwStagingDomainName=www-staging.siutindei.com`,
  `PublicWwwStagingCertificateArn=<74786db9>`. In-place CloudFront alias
  and certificate update on the staging distribution. Staging downtime
  during propagation does not matter.
- `smoke-public-www-staging.yml` and `deploy-public-www.yml` already read
  the hostname from `PublicWwwStagingDomainName`, so they follow the
  parameter. The GitHub `staging` variable `NEXT_PUBLIC_GTM_ALLOWED_HOSTS`
  gains `www-staging.siutindei.com`; Lighthouse runs use the new URL.
- `apps/public_www/README.md`, `docs/architecture/public-www.md`,
  `docs/deployment/launch-checklist.md`, and `params/README.md` drop the
  old staging hostname.

### Staging gate (the evolvesprouts rule, hardened)

Goal: `www-staging.siutindei.com` serves staging only to allow-listed IP
addresses and to CI; everyone else lands on `https://siutindei.com` with
the same path and query, exactly as `www-staging.evolvesprouts.com` does
today.

Worker `siutindei-www-staging-redirect-allowlist`, route
`www-staging.siutindei.com/*`:

1. If `CF-Connecting-IP` is in the allow-list, or the request carries
   `x-staging-bypass` equal to the bypass secret, forward the request to
   the origin with `x-proxy-verify: <staging edge secret>` added.
2. Otherwise respond `302` to `https://siutindei.com` + path + query.

Differences from the evolvesprouts script, each deliberate:

- The allow-list and the two secrets are Worker bindings
  (`STAGING_ALLOWED_IPS`, `STAGING_BYPASS_SECRET`,
  `PUBLIC_WWW_STAGING_EDGE_VERIFY_SECRET`), not literals in the script.
  The source lives in the repository
  (`scripts/cloudflare/workers/www-staging-redirect-allowlist.js`) and is
  uploaded by `edge_policy.py` or Wrangler; the IP list and secrets never
  enter the repository, in line with the no-PII and no-secrets rules.
  The IPs on the evolvesprouts Worker today are visible only to whoever
  can read that script; they are not copied into this document.
- A CI bypass header, so `smoke-public-www-staging.yml` and
  `lighthouse-public-www.yml` keep testing staging. The secret is a GitHub
  `staging` environment secret passed to the smoke script as a request
  header. `smoke-staging.mjs` also asserts that the final URL host after
  redirects is still `www-staging.siutindei.com`, so a missing or rotated
  bypass fails loudly instead of passing against production (the
  evolvesprouts smoke run has this gap).
- The Worker adds `x-proxy-verify`, and the staging distribution is
  deployed with `PublicWwwStagingEdgeVerifySecret` set (parameters and
  CloudFront function already exist from the edge plan). Without that,
  `d2y0sgtf8djbdr.cloudfront.net` stays reachable directly and the gate is
  decorative. Setting the secret also detaches the CloudFront WAF from the
  staging distribution, which is correct once the viewer IP is a
  Cloudflare egress IP.

Why a Worker and not a WAF custom rule: the Free plan has two custom-rule
slots left and no IP Lists (the API returned an authentication error for
lists even with this token); a Worker returns a redirect rather than a
block page, matches evolvesprouts, and can carry the origin-lock header.
Workers Free allows 100k requests a day; staging is nowhere near that.

Cloudflare rule interplay: the three `siutindei.com` custom rules and the
rate limit are path-scoped, so they also run on
`www-staging.siutindei.com/v1/activities/search` once it is proxied. That
is acceptable: staging sends the same `limit` values and the same
`Sec-Fetch-Site` as production. The cache and transform rules are
host-scoped to `siutindei.com` and do not touch staging; the Worker
supplies the origin-lock header instead.

### Domain inventory after the change

Service hostnames only; DKIM, SPF, DMARC, verification TXT, ACM validation
CNAMEs, and MX records are unchanged in all three zones and omitted.

`siutindei.com`:

| Hostname | Role | Proxy | Status |
|---|---|---|---|
| `siutindei.com` | public website (canonical) | orange | unchanged |
| `www.siutindei.com` | 301 → apex (Worker `siutindei-canonical-redirects`) | orange | unchanged |
| `www-staging.siutindei.com` | public website staging, IP allow-list Worker | orange | new |
| `admin.siutindei.com` | admin console (CloudFront) | grey | new |
| `api.siutindei.com` | REST API (API Gateway custom domain) | grey | new |
| `auth.siutindei.com` | Cognito Hosted UI | grey | new |
| `mail.siutindei.com`, `mail.partners.siutindei.com` | SES MAIL FROM | n/a | unchanged |

`evolvesprouts.com` (reference, not changed by this plan):

| Hostname | Role | Proxy |
|---|---|---|
| `evolvesprouts.com` | 301 → `www` (Redirect Rule) | orange |
| `www.evolvesprouts.com` | public website (canonical) | orange |
| `www-staging.evolvesprouts.com` | staging, IP allow-list Worker → 302 `www` | orange |
| `admin.evolvesprouts.com` | admin console (CloudFront) | grey |
| `api.evolvesprouts.com` | REST API; currently `530`/1016 because no API Gateway custom domain backs it | orange |
| `auth.evolvesprouts.com` | Cognito Hosted UI | grey |
| `media.evolvesprouts.com` | asset download (CloudFront) | grey |
| `training.evolvesprouts.com` | training site (CloudFront) | orange |
| `inbound.evolvesprouts.com` | SES inbound mail (MX) | n/a |
| `mail.evolvesprouts.com` | SES MAIL FROM | n/a |
| `bounce.evolvesprouts.com` | Stripe email bounce domain | n/a |

`lx-software.com`:

| Hostname | Role | Proxy | Status |
|---|---|---|---|
| `lx-software.com` | 301 → `www` (Redirect Rule) | orange | unchanged |
| `www.lx-software.com` | company website (CloudFront) | grey | unchanged |
| `admin.lx-software.com` | lx-software admin (CloudFront) | grey | unchanged |
| `auth.lx-software.com` | lx-software Cognito | grey | unchanged |
| `media.lx-software.com` | R2 public bucket | orange | unchanged |
| `inbound.lx-software.com` | SES inbound mail (MX) | n/a | unchanged |
| `siutindei.lx-software.com` | 301 → `https://admin.siutindei.com` (Redirect Rule) | orange | changed, transitional |
| `siutindei-www.lx-software.com` | 301 → `https://siutindei.com` (Worker) | orange | unchanged, retire with the one above |
| `siutindei-api.lx-software.com` | | | removed (phase 4) |
| `siutindei-auth.lx-software.com` | | | removed (phase 2) |
| `siutindei-www-staging.lx-software.com` | | | removed (phase 3) |

After phase 4 the only siutindei names left in `lx-software.com` are the
two redirects, and every siutindei service hostname has an evolvesprouts
twin except the canonical choice (apex here, `www` there) and the
product-specific `media.`, `training.`, `inbound.`, `bounce.` names.

### Invariants worth stating

- `api.siutindei.com` and `auth.siutindei.com` stay DNS-only. The
  `siutindei.com` custom rules (`search-limit-allowlist`,
  `search-sec-fetch-site`, `search-tooling-user-agents`) and the rate limit
  match on path only, so a proxied API hostname would have legitimate
  partner and mobile requests blocked by rules written for the website.
  If a hostname is ever proxied, those rules must first gain a
  `http.host eq "siutindei.com"` guard (the rate limit rule cannot on Free).
- Cognito's CloudFront requires SNI and sets its own cookies; a DNS-only
  record is the supported shape.
- `X-Origin-Verify`, the attestation tokens, the edge-verify secret, the
  API WAF, and the user pool id and client ids are unchanged. No user
  re-registers and no mobile deep-link scheme changes.

## Rollout order

Phase 0, prerequisites (operator, console):

1. Request the `ap-southeast-1` certificate; confirm `Issued`.
2. Google and Apple redirect URIs for `auth.siutindei.com`.
3. Cloudflare token with DNS:Edit on `siutindei.com` and `lx-software.com`,
   Redirect Rules edit on `lx-software.com`, and Workers Scripts:Edit on
   the account.
4. Decide the staging allow-list IPs (the evolvesprouts Worker's list is
   the starting point) and generate `STAGING_BYPASS_SECRET` and
   `CDK_PARAM_PUBLIC_WWW_STAGING_EDGE_VERIFY` with
   `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

Phase 1, API in parallel (zero downtime):

1. Merge the CDK change (secondary domain, CORS defaults, callback URLs,
   amplify config). `cdk-diff.yml` must show only additions in the API
   stack.
2. Deploy `lxsoftware-siutindei` with `ApiSecondaryCustomDomainName` set.
3. Create `api.siutindei.com` CNAME from `ApiSecondaryCustomDomainTarget`.
   Verify `curl -sI https://api.siutindei.com/v1/health` matches the old
   host and the certificate is `*.siutindei.com`.
4. Set `SearchApiProxyOriginDomain=api.siutindei.com`, deploy
   `lxsoftware-siutindei-public-www`. Verify a search on `siutindei.com`
   returns 200 (`cf-cache-status: DYNAMIC`, no 403 from the origin).
5. Update `NEXT_PUBLIC_API_BASE_URL`; the admin rebuild happens in phase 3.

Phase 2, Cognito (maintenance window, about one hour):

1. Announce. Deploy A, then Deploy B as above.
2. Create `auth.siutindei.com`; verify
   `https://auth.siutindei.com/login?client_id=…&response_type=code&redirect_uri=https://admin.siutindei.com/auth/callback`
   renders and `/.well-known/openid-configuration` is served.
3. Delete `siutindei-auth.lx-software.com`.

Phase 3, admin console and staging (same deploy run, `cdk_stacks` admin-web
and public-www):

1. Add the Cloudflare Redirect Rule and flip `siutindei.lx-software.com`
   to proxied. Create `admin.siutindei.com` CNAME.
2. Deploy `lxsoftware-siutindei-admin-web` with the new alias and
   certificate. Run `deploy-admin-web.yml` with the new variables.
3. Verify sign-in with Google, Apple, and email OTP on
   `https://admin.siutindei.com`, one admin API call, and that
   `https://siutindei.lx-software.com/admin/dashboard` returns 301 to the
   new host.
4. Staging: upload the Worker with its bindings, add the route
   `www-staging.siutindei.com/*`, create the proxied CNAME. Deploy
   `lxsoftware-siutindei-public-www` with `PublicWwwStagingDomainName`,
   its certificate, and `PublicWwwStagingEdgeVerifySecret` set. Merge the
   `smoke-staging.mjs` bypass-header and host assertion first, and add
   the `STAGING_BYPASS_SECRET` to the GitHub `staging` environment.
5. Verify from an allow-listed IP: `200` with `server: cloudflare`. From
   anywhere else: `302` to `https://siutindei.com/en/`. Direct:
   `curl -sI https://d2y0sgtf8djbdr.cloudfront.net/en/ -H 'Host: www-staging.siutindei.com'`
   returns `403`. Run `smoke-public-www-staging.yml`; it must report the
   staging host in every PASS line.
6. Delete `siutindei-www-staging.lx-software.com`.

Phase 4, retirement (after the mobile builds and the board importer have
moved; at least one admin-web release later):

1. Swap the parameter wiring so `ApiCustomDomainName=api.siutindei.com`
   drives the surviving construct; remove the secondary parameters. Drop
   the `lx-software.com` origins from both CORS defaults; update
   `tests/test_search_handler.py` to the new origin.
2. Delete `siutindei-api.lx-software.com` from Cloudflare. Keep the
   `siutindei.lx-software.com` redirect for as long as bookmarks matter.
3. Remove the old Google and Apple redirect URIs.
4. Update docs: `docs/deployment/admin-web.md`,
   `docs/deployment/launch-checklist.md` §6 table,
   `docs/architecture/security.md` CORS list,
   `docs/architecture/aws-assets-map.md`,
   `docs/architecture/public-www.md`, and the Google redirect example in
   `docs/architecture/setup.md`.

## Files

- `docs/plans/siutindei-domain-consolidation.md` (this plan)
- `backend/infrastructure/lib/api-stack.ts` (secondary API domain, CORS
  defaults)
- `backend/infrastructure/params/production.json`
- `backend/src/app/utils/responses.py` (CORS defaults)
- `scripts/deploy/build_amplify_config.py`,
  `tests/test_build_amplify_config.py`
- `scripts/ops/board-importer`
- `tests/test_search_handler.py` (phase 4)
- `scripts/cloudflare/workers/www-staging-redirect-allowlist.js` (new) and
  a `node --test` for its allow-list, bypass, and redirect branches
- `scripts/cloudflare/edge_policy.py` if the Worker upload is added as a
  section; otherwise Wrangler with a config outside the secrets
- `apps/public_www/scripts/smoke-staging.mjs` (bypass header, host
  assertion) and `.github/workflows/smoke-public-www-staging.yml`,
  `.github/workflows/lighthouse-public-www.yml` (pass the secret)
- No change to `.github/workflows/deploy-backend.yml`:
  `CDK_PARAM_PUBLIC_WWW_STAGING_EDGE_VERIFY` is already passed through;
  only the GitHub secret needs a value
- `apps/public_www/README.md`, `backend/infrastructure/params/README.md`
- `docs/deployment/admin-web.md`, `docs/deployment/launch-checklist.md`,
  `docs/architecture/security.md`, `docs/architecture/aws-assets-map.md`,
  `docs/architecture/public-www.md`, `docs/architecture/setup.md`,
  `docs/plans/cloudflare-edge-protection.md` (step 8 now points here)

## Invariants this change preserves

- The public website's static-export contract and its Cloudflare edge
  policy are untouched; the apex record and rulesets do not change.
- The API stage, WAF, authorizers, and shared secrets are unchanged; only
  hostnames in front of them change.
- Secrets stay out of the repository. The new certificate ARN is not a
  secret; everything else arrives through the existing `CDK_PARAM_*` path.
- With the new parameters empty, the API stack synthesises the same
  template as today, so `cdk-diff.yml` on the code change alone is empty
  apart from the two new parameters and outputs.

## Done when

- Phase 1: `npm run build` in `backend/infrastructure` passes; `pytest
  tests/test_build_amplify_config.py tests/test_search_handler.py` passes;
  `cdk-diff.yml` shows additions only; `curl -sI https://api.siutindei.com/v1/health`
  and the same call on the old host return identical status.
- Phase 2: the Hosted UI renders on `auth.siutindei.com`; an admin signs
  in with each provider.
- Phase 3: `curl -sI https://admin.siutindei.com/` returns 200 with a
  `*.siutindei.com` certificate; `curl -sI https://siutindei.lx-software.com/`
  returns 301 with `location: https://admin.siutindei.com/`;
  `curl -sI https://www-staging.siutindei.com/en/` from a non-listed IP
  returns 302 to `https://siutindei.com/en/`, with the bypass header
  returns 200, and the direct CloudFront hostname returns 403;
  `node --test` on the Worker passes; `smoke-public-www-staging.yml` is
  green and every PASS line names the staging host.
- Phase 4: no `lx-software.com` hostname remains in
  `params/production.json`, the CORS defaults, or the Cloudflare
  `lx-software.com` zone except the admin redirect.

## Rollback

- Phase 1: set `ApiSecondaryCustomDomainName=""` and redeploy; delete the
  `api.siutindei.com` record. Set `SearchApiProxyOriginDomain` back to the
  old host if step 4 ran.
- Phase 2: redeploy with `CognitoCustomDomainName=siutindei-auth.lx-software.com`
  and the `ea553e5a` certificate (same two-deploy dance in reverse),
  recreate the `siutindei-auth` CNAME from the new output value. Rollback
  costs the same window as the change.
- Phase 3: redeploy admin-web with the old alias and certificate, turn
  `siutindei.lx-software.com` grey again, disable the Redirect Rule.
  Staging: remove the Worker route (staging is then open again but still
  on the new hostname), or redeploy public-www with the old staging alias
  and an empty `PublicWwwStagingEdgeVerifySecret` and recreate the old
  record. Remove the route before clearing the edge secret, otherwise the
  Worker's header is rejected for the deploy duration.
- Phase 4: re-add the retired parameters and records; nothing is
  destroyed that cannot be recreated from this plan.

## Open questions

- Approve the hostnames `admin.`, `api.`, `auth.`, and
  `www-staging.siutindei.com`, and the maintenance window for phase 2.
- Keep the apex as the canonical public hostname, or flip to `www.` for a
  one-to-one match with evolvesprouts? Flipping costs a redirect of every
  indexed URL and a change to every canonical tag; the recommendation is
  to keep the apex.
- Which IP addresses go on the staging allow-list, and should the
  evolvesprouts Worker be upgraded to the same binding-based script so the
  two gates stay identical?
- Should `api.evolvesprouts.com` be fixed in the sibling repository (it
  needs an `ApiCustomDomainName` and a grey record, as planned here) or
  removed?
- Should the `siutindei.lx-software.com` redirect be permanent or removed
  after a fixed period?
- Should the new Cloudflare records be captured as code by extending
  `scripts/cloudflare/edge_policy.py` to a record list, or is the
  launch-checklist table enough? The tool is single-hostname today.
- Whether to grant the `cursor-cloud-agent` IAM user the read-only
  permissions listed in the audit so later phases can be verified from a
  Cloud Agent.
