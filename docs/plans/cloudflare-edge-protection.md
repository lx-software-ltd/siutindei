# Plan: Cloudflare edge protection for the public website

**Status**: Applied. Rollout steps 1-5 and 7 applied on 2026-11-02
(settings, four rulesets, AI-bot block, apex proxied, production origin
lock deployed). Staging origin lock applied on 2026-11-09 (Worker
`PUBLIC_WWW_STAGING_EDGE_VERIFY_SECRET` plus
`PublicWwwStagingEdgeVerifySecret`; Access was not used). The first lock
deploy took the site down: the header was named `x-edge-verify`, and
CloudFront strips every `X-Edge-*` header before edge functions run, so
no request could ever match. The header is now `x-proxy-verify`, and
`public-www-edge-verify.test.mjs` fails if the name ever falls into
CloudFront's disallowed set or drifts from the Cloudflare policy file.
**Zone**: red (touches `backend/infrastructure/**`); the Cloudflare policy
tool, the public website, and the docs are green.

## Goal

Make bulk extraction of the activity catalogue through `siutindei.com`
slow, noisy, and detectable while keeping every page indexable and every
real visitor unaffected. The site stays a static export on CloudFront.
Cloudflare, on the **Free** plan, becomes the only public entry point and
the only place that sees the real client IP, so it is where rate limits,
request-shape rules, bot heuristics, and AI-crawler blocking live.
CloudFront refuses anything that did not come through Cloudflare.

Cloudflare configuration becomes code: a desired-state file plus a
plan/apply tool, so the rules are reviewable in a pull request and
reproducible on staging.

## Non-goals

- Making public data private. Cards stay public and crawlable by search
  engines; this plan changes the cost of a dump, not what a dump contains.
- Changing what the search API returns (field minimisation, per-credential
  `limit` caps). That is backend work tracked separately.
- Obfuscating HTML, JavaScript, or text. It breaks SEO, accessibility,
  zh-HK rendering, the strict CSP, and is reversed in an afternoon.
- Paid Cloudflare features (Super Bot Fight Mode, Bot Management scores,
  rate-limit windows longer than 10 s, more than one rate-limit rule).
- A mobile client. None exists today; the API Gateway custom domain keeps
  its own attestation and regional WAF regardless.

## What the live audit found (2026-11-02, read-only API calls)

Account tokens `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` were
used read-only. Zone `siutindei.com` is on **Free Website**.

| Item | Current value | Consequence |
|---|---|---|
| `siutindei.com` CNAME | `d2zpx4ub70d0qj.cloudfront.net`, **proxied: false** | Cloudflare is not in the request path. No rule can act. |
| `www.siutindei.com` CNAME | same target, proxied: true, Worker `siutindei-canonical-redirects` | Already proxied; only serves 301s. |
| `siutindei-www-staging.lx-software.com` (zone `lx-software.com`) | `d2y0sgtf8djbdr.cloudfront.net`, proxied: false | Staging fixture `/fixtures/activity_search_staging.json` is reachable by anyone who knows the hostname. |
| SSL mode | `full` | Origin certificate not validated. Needs `strict` (sister zone `evolvesprouts.com` already uses `strict`). |
| `email_obfuscation` | on | Injects an inline script into HTML; breaks the hash-based CSP meta once proxied. |
| `browser_cache_ttl` | 14400 | Cloudflare would lengthen the 300 s browser TTL on HTML; deploys would look stale for 4 h. |
| `rocket_loader`, `minify`, `mirage`, `polish` | off | Good; leave off. |
| `browser_check`, `always_use_https`, `security_level=medium` | on | Good; leave on. |
| Rulesets | only Cloudflare managed (normalisation, free managed WAF, DDoS L7) | No custom, rate-limit, cache, or transform rules exist. Clean slate. |
| Bot management | token lacks permission (`Authentication error`) | Bot Fight Mode and AI-bot blocking cannot be read or set with this token. |
| Access (Zero Trust) | not enabled on the account | Staging cannot be put behind Access until it is enabled in the dashboard. |
| Turnstile widgets | one for `evolvesprouts` only | A `siutindei` widget does not exist yet. |
| CAA records | none | Cloudflare Universal SSL and ACM renewals are both free to issue. |
| CloudFront WAF | `WafWebAclArn` set in `params/production.json`; rule `RateLimitRule` 1000 req / 5 min per **viewer IP** | After proxying, the viewer IP is a Cloudflare egress IP. Real users would be aggregated and blocked together. Must be detached from the public distributions. |

Token permissions observed: zone list, DNS read, zone settings read,
rulesets list, Workers read, Turnstile read. Missing for apply: Zone WAF
edit, Transform Rules edit, Cache Rules edit, Bot Management edit, DNS
edit, Zone Settings edit, and (later) Access and Turnstile edit.

## Free-plan facts the design is built on

From the Cloudflare docs availability tables, fetched during the audit:

- Rate limiting rules: **1 rule**, expression may only use **path and
  verified bot**, counting period **10 s**, mitigation timeout **10 s**,
  action block, counted per IP.
- Custom (WAF) rules: **5 rules**, all request fields, all actions except
  Log, **no regex**.
- Cache Rules: 10. Transform Rules: 10, no regex.
- Bot Fight Mode: free, zone-wide, **cannot be scoped or skipped** by
  custom rules, auto-enables JavaScript Detections, which injects an
  inline script that a `<meta>` CSP without nonces will refuse. Cloudflare
  states JSD "is not supported with nonce set via `<meta>` tags".
- Managed Challenge returned to a `fetch()` call is an HTML page the site
  cannot parse. Challenges are therefore only safe on HTML navigations.

## Design

### Request path after the change

```
browser ──TLS──> Cloudflare edge (siutindei.com, orange cloud)
                   │ Always HTTPS, Browser Integrity Check, DDoS
                   │ rate limit  (/v1/activities/search, per IP, 10 s)
                   │ custom rules (limit allow-list, Sec-Fetch-Site, tooling UAs)
                   │ cache rules (bypass; only /_next/static/* cacheable)
                   │ transform   (adds x-proxy-verify: <secret>)
                   ▼
                 CloudFront d2zpx4ub70d0qj  (SSL strict, Host preserved)
                   │ viewer-request functions reject when x-proxy-verify
                   │ does not match the current or previous secret
                   ├── default behaviour ─> S3 static export
                   ├── /v1/activities/search ─> API Gateway (+X-Origin-Verify)
                   └── /v1/listing-events   ─> API Gateway (+X-Origin-Verify)
```

### Cloudflare desired state (`scripts/cloudflare/public_www_edge_policy.json`)

Zone settings:

| Setting | Desired | Why |
|---|---|---|
| `ssl` | `strict` | Validate the ACM certificate CloudFront presents. |
| `email_obfuscation` | `off` | No edge HTML rewriting; CSP hashes must keep matching. |
| `browser_cache_ttl` | `0` (respect origin) | HTML keeps `max-age=300`; deploys stay visible. |
| `rocket_loader` | `off` | Same reason. |
| `always_use_https` | `on` | Unchanged. |
| `browser_check` | `on` | Blocks missing or abusive User-Agents before any rule. |

Rate limit (phase `http_ratelimit`, the one Free rule):

- Expression `http.request.uri.path eq "/v1/activities/search"`, 15
  requests per 10 s per IP, block for 10 s. The home page issues three
  search fetches on load (24 + 12 + 12 items) and the search page one per
  interaction, so humans stay well below 15. A dump of the 3,780-item
  staging fixture at 30 items per request needs 126 requests and is forced
  to crawl at about one request per second; see "What this does not solve".

Custom rules (phase `http_request_firewall_custom`, 3 of the 5 slots):

1. `search-limit-allowlist`: block `/v1/activities/search` unless `limit`
   is exactly one of the values the site sends (`1`, `12`, `24`, `30`;
   source `apps/public_www/src/lib/activities/search-limits.ts` and
   `fetchActivityListingById`). The backend accepts up to 200, so this is
   what caps a page at 30 at the edge. A vitest contract test keeps the
   allow-list and the TypeScript constants in sync.
2. `search-sec-fetch-site`: block `/v1/activities/search` when the
   `Sec-Fetch-Site` header is present and is not `same-origin`. Browsers
   set it on every fetch the site makes; a tab opened on the API URL
   (`none`) or a third-party page embedding the call is refused. Requests
   without the header (pre-2023 Safari) still pass, so no legacy browser is
   locked out.
3. `search-tooling-user-agents`: block `/v1/activities/search` when the
   User-Agent is empty or contains common HTTP-library and headless
   markers (`python`, `curl/`, `wget/`, `go-http-client`, `scrapy`,
   `httpx`, `aiohttp`, `java/`, `okhttp`, `node-fetch`, `axios/`,
   `headlesschrome`, `phantomjs`, `puppeteer`, `playwright`, `selenium`).
   Lighthouse CI and the staging smoke runner do not hit this hostname.

Two slots stay free for a Turnstile pre-clearance rule and a staging
rule later.

Cache rules (phase `http_request_cache_settings`):

1. `static-assets-cacheable`: `/_next/static/*` eligible, edge and browser
   TTL respect origin (those files are content-hashed).
2. `bypass-everything-else`: every other request bypasses the Cloudflare
   cache. CloudFront remains the only cache, so `deploy-public-www.sh`
   invalidations keep working and the 5-minute search cache is not
   doubled.

Transform rule (phase `http_request_late_transform`):

- `edge-verify-header`: set request header `x-proxy-verify` to the value of
  `PUBLIC_WWW_EDGE_VERIFY_SECRET` on every request to `siutindei.com`. The
  value is read from the environment at apply time; the policy file holds
  the placeholder `${PUBLIC_WWW_EDGE_VERIFY_SECRET}` and the tool refuses
  to apply that rule while the variable is unset.

Bot management:

- `ai_bots_protection: block`. Enforced blocking of GPTBot, CCBot,
  Bytespider and the rest of Cloudflare's AI crawler list.
- `fight_mode: false` for now. Reasons: it cannot be scoped away from the
  same-origin search fetch and has no Free-plan skip, so a false positive
  turns into a broken search for that visitor; and its JavaScript
  Detections inline script is refused by the `<meta>` CSP, producing a
  console error on every page and a Lighthouse best-practices hit. Revisit
  after two weeks of Security Analytics show what the custom rules miss.

DNS:

- `siutindei.com` CNAME `proxied: true`. Applied last, as its own step.

### CloudFront origin lock (`backend/infrastructure/lib/public-www-stack.ts`)

Once the apex is proxied, `d2zpx4ub70d0qj.cloudfront.net` is still a
public hostname and the DNS history still shows it. Without a lock every
Cloudflare rule is decorative for anyone who finds it.

- Two new parameters mirroring the existing `PublicWwwOriginVerifySecret`
  pattern: `PublicWwwEdgeVerifySecret` and
  `PublicWwwEdgeVerifySecretPrevious` (`noEcho`, default empty, minimum 32
  characters when set). Both empty means **no enforcement**, so the stack
  deploys unchanged until the operator opts in. Two values allow rotation
  without a window where traffic is refused.
- Every viewer-request function on the public distributions (path rewrite,
  search allow-list, listing-events allow-list) first checks the
  `x-proxy-verify` header against the configured values and returns `403`
  otherwise. The check is shared code prepended to each function body
  because CloudFront allows one viewer-request function per behaviour.
- Staging gets its own pair (`PublicWwwStagingEdgeVerifySecret`,
  `PublicWwwStagingEdgeVerifySecretPrevious`) so the two distributions can
  be locked independently.
- WAF detachment is not a separate switch. The condition
  `<Prefix>AttachWaf = HasWafWebAclArn AND NOT Has<Prefix>EdgeVerifySecret`
  drops `WafWebAclArn` from a distribution in the same deploy that enables
  its edge secret: the shared CloudFront WebACL rate rule counts by viewer
  IP, which is a Cloudflare egress IP after the flip. Cloudflare provides
  the equivalent managed rules and rate limiting from then on.
- Parameter defaults keep the stack diff empty for anyone who has not set
  the new parameters. `params/production.json` gains the four keys with
  `<FROM_GITHUB_SECRET: ...>` placeholders, the same convention the origin
  verify secret uses, and `deploy-backend.yml` passes them through from
  `CDK_PARAM_PUBLIC_WWW_[STAGING_]EDGE_VERIFY[_PREVIOUS]`.

### Public website (`apps/public_www`)

- `robots.txt`: disallow `/v1/` and `/cdn-cgi/` for every agent. The API
  is not a page and `/cdn-cgi/` is Cloudflare's challenge platform. AI
  crawlers are blocked at the edge rather than by advisory robots rules.
- `tests/lib/cloudflare-edge-policy.test.ts`: asserts the Cloudflare
  `limit` allow-list equals the set of limits the site actually sends.
- No CSP change in this phase. With Bot Fight Mode off and Turnstile not
  yet deployed, nothing from `challenges.cloudflare.com` loads. The
  Turnstile phase adds `https://challenges.cloudflare.com` to
  `script-src`, `frame-src`, and `connect-src` in `inject-csp-meta.mjs`.

## Rollout order

Each step is independently reversible. Steps 1-5 are applied; step 6
(observation) is running; steps 7-9 are pending.

1. **Token.** Create a Cloudflare API token scoped to zone
   `siutindei.com` with Zone Settings:Edit, DNS:Edit, Zone WAF:Edit,
   Transform Rules:Edit, Cache Rules:Edit, Bot Management:Edit, and store
   it as the Cloud Agent / GitHub secret `CLOUDFLARE_API_TOKEN`. Generate
   `PUBLIC_WWW_EDGE_VERIFY_SECRET` (`openssl rand -base64 48`), store it
   where the CDK parameters are sourced (`CDK_PARAM_PUBLIC_WWW_EDGE_VERIFY`).
2. **Dry run.** `python3 scripts/cloudflare/edge_policy.py plan` shows
   every intended change against the live zone. Expected: three settings,
   four rulesets created, bot management updated, DNS still grey.
3. **Cloudflare, apex still grey.**
   `edge_policy.py apply --yes --section settings --section rulesets --section bot`.
   No traffic flows through Cloudflare yet, so the rules are inert. This
   is the moment to read the rules back in the dashboard.
4. **CDK deploy with enforcement off.** Deploy `PublicWwwStack` with the
   new parameters at their defaults. The only change is the function code
   now containing the (inactive) edge check. Confirm the site still
   serves.
5. **Flip.** `edge_policy.py apply --yes --section dns`. Within a minute
   `curl -sI https://siutindei.com/en/` shows `server: cloudflare` and
   `cf-ray`. Check: home page, `/zh-HK/`, search with filters, an activity
   detail page, `/sitemap.xml`, `/robots.txt`, one search fetch with
   DevTools open (status 200, `cf-cache-status: DYNAMIC`).
6. **Observe for a day.** Security Analytics: rate-limit matches should be
   zero or single digits; custom rule matches should be only non-browser
   clients. If a real client pattern is blocked, lower the rule, not the
   plan.
7. **Lock the origin.** Deploy `PublicWwwStack` with
   `PublicWwwEdgeVerifySecret` set; the WAF WebACL detaches from the
   production distribution in the same deploy. Verify `curl -sI https://d2zpx4ub70d0qj.cloudfront.net/en/ -H 'Host: siutindei.com'`
   returns `403` and `https://siutindei.com/en/` still returns `200`.
8. **Staging** (done 2026-11-09, not Access): Worker
   `siutindei-www-staging-redirect-allowlist` on
   `www-staging.siutindei.com/*` sets `x-proxy-verify` from
   `PUBLIC_WWW_STAGING_EDGE_VERIFY_SECRET`. The staging CloudFront
   distribution enforces `PublicWwwStagingEdgeVerifySecret`. Direct
   `d2y0sgtf8djbdr.cloudfront.net` returns 403. Zero Trust Access stays
   unused (`access.api.error.not_enabled` on the account).
9. **Turnstile** (later, separate plan): create a `siutindei` widget
   (invisible mode, pre-clearance on), render it on the home and search
   pages, send the token as `x-turnstile-token`, and verify it either in a
   Worker on `siutindei.com/v1/activities/search*` (no AWS change) or in the
   device-attestation authorizer (red zone). This replaces the static
   `NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN` that anyone can copy from the
   bundle.

## Files

- `docs/plans/cloudflare-edge-protection.md` (this plan)
- `scripts/cloudflare/edge_policy.py` (plan/apply tool, stdlib only)
- `scripts/cloudflare/public_www_edge_policy.json` (desired state)
- `tests/test_cloudflare_edge_policy.py`
- `backend/infrastructure/lib/public-www-stack.ts`
- `backend/infrastructure/lib/functions/public-www-path-rewrite.js`
- `backend/infrastructure/lib/functions/public-www-edge-verify.js`
- `backend/infrastructure/test/public-www-path-rewrite.test.mjs`
- `backend/infrastructure/test/public-www-edge-verify.test.mjs`
- `backend/infrastructure/params/production.json`
- `.github/workflows/deploy-backend.yml`
- `apps/public_www/src/app/robots.ts`
- `apps/public_www/src/lib/routes.ts`
- `apps/public_www/tests/lib/cloudflare-edge-policy.test.ts`
- `apps/public_www/tests/app/robots.test.ts`
- `docs/architecture/public-www.md`
- `docs/deployment/launch-checklist.md`

## Invariants this change preserves

- The static-export contract: no server actions, no SSR, no API routes.
- Googlebot and Bingbot keep crawling pages. No rule targets verified
  bots; the rate limit is path-scoped to the API.
- The search fetch from the site's own pages is never challenged. Only
  block actions are used on `/v1/activities/search`.
- CloudFront remains the single cache for HTML and the search API.
  `deploy-public-www.sh` invalidations keep their meaning.
- `X-Origin-Verify` between CloudFront and API Gateway is unchanged.
- With both edge-verify parameters empty, the CloudFront stack behaves
  exactly as today.
- Secrets are never in the repository. The policy file carries an
  environment placeholder; the CDK parameters are `noEcho`.

## Done when

- `python3 scripts/cloudflare/edge_policy.py plan` runs against the live
  zone and prints the intended diff without writing (evidence in the
  pull request).
- `pytest tests/test_cloudflare_edge_policy.py` passes.
- `npm run lint` and `npm test` pass in `apps/public_www`.
- `npm run build` passes in `backend/infrastructure`;
  `node --test test/*.test.mjs` passes for the CloudFront functions.
- After rollout step 7, the direct CloudFront hostname returns 403 and
  the apex returns 200.

## Rollback

- Cloudflare: `edge_policy.py apply --yes --section dns --proxied false`
  turns the apex grey again within a minute; TLS falls back to the ACM
  certificate directly. Rulesets can be left in place; they are inert
  without proxied traffic.
- CloudFront: redeploy with `PublicWwwEdgeVerifySecret` empty; the
  functions stop checking the header and the WAF WebACL re-attaches. Do rollback of CloudFront **before** the DNS rollback if both are
  needed, otherwise direct traffic is refused for the deploy duration.

## What this does not solve

- A patient scraper with residential proxies and a real browser stays
  under 15 requests per 10 s per IP and gets the catalogue in a few hours
  instead of a few seconds. Detection (Security Analytics, CloudFront
  logs) is what you gain against that actor, not prevention.
- Anything Google indexes is readable through Google.
- The structured data a successful request returns is unchanged until the
  backend field-minimisation work lands.

## Open questions

- Confirm the operator is comfortable with the edge secret being visible
  in the Cloudflare dashboard (Transform Rule value) and the CloudFront
  Function code (same exposure as today's origin custom header).
- Enable Bot Fight Mode after the observation period, accepting the CSP
  console error, or keep relying on the custom rules.
- Whether to add `Sec-Fetch-Site` enforcement to `/v1/listing-events` as
  well once the search rule has a clean week.
