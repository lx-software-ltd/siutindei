# Public Website (`apps/public_www`)

This document describes the design, hosting topology, security model, and
deployment lifecycle of the Siu Tin Dei marketing/public website.

## Goals

1. Serve a fast, statically-rendered marketing site to anonymous users.
2. Provide an isolated **staging** environment that mirrors production
   exactly so we can validate releases before promoting them.
3. Make production promotion **rebuild-or-copy**: either rebuild with
   production env vars (default) or perform an S3-only artifact copy from
   the staging bucket (cheaper, faster, byte-for-byte identical artifact).
4. Default-deny indexing on staging so search engines never see a draft.

## Hosting topology

One CloudFormation stack — `lxsoftware-siutindei-public-www` — provisions
**two parallel website environments** (production + staging). Each
environment has:

| Resource | Notes |
|---|---|
| S3 origin bucket | `BlockPublicAccess: BLOCK_ALL`, SSL-only, versioned, retain on delete, S3-managed encryption, server access logging into the logging bucket. |
| S3 logging bucket | Same hardening, 90-day expiration lifecycle, 30-day non-current expiration. |
| CloudFront Origin Access Identity | Restricts S3 reads to the distribution. |
| CloudFront Distribution | TLS 1.2 (2021), HTTP/2 + HTTP/3, CloudFront access logs into the logging bucket, `defaultRootObject=index.html`, custom 4xx → `/404.html`. |
| CloudFront Function (`pathRewriteFunction`) | Maps `/foo/` and `/foo` → `/foo/index.html` for Next.js `output: 'export'`. |
| Response Headers Policy | HSTS (`max-age=31536000; includeSubDomains; preload`), CSP (`base-uri 'self'; object-src 'none'; frame-ancestors 'none'`), `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Content-Type-Options`, `XSS-Protection`, restrictive `Permissions-Policy`, and `X-Robots-Tag: noindex,nofollow,noarchive` on **staging only**. |
| WAF (optional) | Reuses the admin web WebACL ARN from `params/production.json`. Attached via `CfnCondition` so the stack can deploy to lower environments before the WAF is created. |

CDK source: [`backend/infrastructure/lib/public-www-stack.ts`](../../backend/infrastructure/lib/public-www-stack.ts).
Stack registration: [`backend/infrastructure/bin/app.ts`](../../backend/infrastructure/bin/app.ts).

### Custom domains

Configured via `backend/infrastructure/params/production.json` and passed to
CloudFront as alternate domain names (CNAMEs). Production uses a dedicated
`us-east-1` ACM certificate covering `siutindei.com` and `*.siutindei.com`.
Staging reuses the shared `lx-software.com` certificate. Hostnames must be
listed on the certificate attached to that distribution.

| Environment | CloudFront alias |
|---|---|
| Production | `siutindei.com` |
| Staging | `siutindei-www-staging.lx-software.com` |

`www.siutindei.com` and the legacy `siutindei-www.lx-software.com` hostname
301 to the apex at the Cloudflare edge (Worker
`siutindei-canonical-redirects`). Do not add those names as CloudFront
aliases unless the attached certificate covers them.

### Resource naming

Both environments respect the 63-char S3 bucket name limit:

| Logical id | Physical name pattern | Length math (`ap-southeast-1`) |
|---|---|---|
| `PublicWwwBucket` | `lxsoftware-siutindei-www-{account12}-{region}` | 24+1+12+1+14 = 52 ≤ 63 |
| `PublicWwwLoggingBucket` | `lxsoftware-siutindei-www-logs-{account12}-{region}` | 29+1+12+1+14 = 57 ≤ 63 |
| `PublicWwwStagingBucket` | `lxsoftware-siutindei-stg-www-{account12}-{region}` | 28+1+12+1+14 = 56 ≤ 63 |
| `PublicWwwStagingLoggingBucket` | `lxsoftware-siutindei-stg-www-logs-{account12}-{region}` | 33+1+12+1+14 = 61 ≤ 63 |

Note the staging prefix uses `stg` (not `staging`) to leave headroom.

## Application

Source: [`apps/public_www`](../../apps/public_www).

- Next.js (App Router) with `output: 'export'`.
- TypeScript only.
- Tailwind CSS v4 via `@tailwindcss/postcss`.
- Vitest + Testing Library for unit/component tests.
- Lighthouse CI configured at `apps/public_www/.lighthouserc.json`.
- Build script: `next build` → `inject-static-redirects.mjs` →
  `inject-html-lang.mjs` → `inject-csp-meta.mjs` → `validate-csp-meta.mjs`.

### Page composition (evolvesprouts-aligned)

- **Locales:** `src/content/en.json`, `zh-HK.json`, … with routes under
  `src/app/[locale]/…` and root redirects (`/` → `/en/`).
- **Template:** `[locale]/layout.tsx` wraps routes with `PageLayout`
  (`Navbar` header + `<main>` + `Footer`). Mobile drawer nav; WhatsApp FAB
  on small screens, footer link on larger breakpoints.
- **Body:** Marketing pages (for example About) still use `pages.<pageKey>.body`
  with the 12-column CSS grid (`rows` → `cells` with `component`, `colStart`,
  `colSpan`, optional `props`) in `src/components/sections/grid/page-body-grid.tsx`.
  The home route renders `DiscoveryHomePage` (Airbnb-style discovery: the
  immersive "Small World" hero, a 3-step search navigator in the hero, and
  horizontal listing carousels fed by `/v1/activities/search`).
- **Brand & immersive homepage:** the "Small World" brand system lives in
  the `@theme` tokens in `src/app/globals.css` (golden-yellow base with
  earth-teal / leaf-green support colors and chocolate ink, sampled from
  the logo artwork), the cropped source logo assets (mark, wordmark,
  stacked lockup) and badge SVGs in `public/images/brand/`, a favicon
  copied from the logo mark (`public/favicon.svg` plus a multi-size
  `public/favicon.ico`). The navbar pairs the mark with the wordmark and
  stays sticky on inner pages. On the home route it stays off-screen
  until the hero search box scrolls out of view, then slides down. The
  hero and footer use the stacked lockup. Category icons
  are the kawaii outline-style isometric SVGs in
  `public/images/categories/`.
  Display titles use the brand face Aero BC (`--font-display`,
  `.brand-title`: letter-spacing 0.09em, 52px at desktop) with rounded
  system fallbacks; the licensed webfont file is not committed. The hero
  (`src/components/sections/hero/small-world-hero.tsx`) shows a random
  subset of 20 original kawaii pictures cropped from the Hong Kong icon
  sheet (`public/images/small-world/bubble-*.webp`): 6 on large screens
  and 3 otherwise, with a CSS drift only. There is no WebGL / three.js
  upgrade. A
  canvas-based sparkle cursor trail
  (`src/components/shared/sparkle-cursor.tsx`) is mounted from the locale
  layout for fine-pointer devices. No CSP changes are required: everything
  is same-origin static JS and `<canvas>` rendering.
- **Search & detail:**   `/[locale]/search/` opens the Google Maps split view
  when maps are enabled (explicit `?view=map`, or no `view` param). `?view=list`
  is the results grid. Search, See all, and discovery carousel links land on
  the map. The map canvas mounts as soon as the search page opens (including
  the first results fetch) so the Maps script can load in parallel. Script
  load waits until `importLibrary` / `Map` exist; `script.onload` alone is
  not enough because `loading=async` can fire before `window.google.maps` is
  assigned. Pins use the activity-type icons (workshop / class / outdoor /
  indoor). Below the `lg` breakpoint the map is full-width with pins for
  the filtered results and a selected-activity summary card at the bottom.
  Tapping a pin selects that activity; tapping the card opens the activity
  detail page. From `lg` (iPad landscape and computer) the default is a 50/50
  list + map split, with enlarge/reduce controls to switch into the mobile
  map+card layout and back. Activity detail is `/[locale]/activity/?id=<uuid>`
  (detail + WhatsApp CTA). Optional `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` enables
  Static Maps on listing cards, map markers on the search map view, and CSP
  entries for
  `maps.googleapis.com` / `maps.gstatic.com`. The search bar **area** label links
  to the map view for the selected region. Search uses browser-side `fetch` to
  `NEXT_PUBLIC_SEARCH_API_BASE_URL` unless
  `NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED=true`, in which case listings are
  loaded at runtime from
  `{NEXT_PUBLIC_SITE_ORIGIN}/fixtures/activity_search_staging.json` (static
  file copied from `shared/fixtures/` during the staging deploy build; canonical
  source is Git LFS). Controlled only on the **staging** public website build
  via GitHub Environment variable `STAGING_SEARCH_DATA_ENABLED` (defaults to
  `true` when unset). Production promote always sets
  `NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED=false` and uses the live search API
  / Aurora. Optional override on staging:
  `NEXT_PUBLIC_STAGING_SEARCH_FIXTURE_URL`.
  CSP `connect-src` includes the API origin only when that URL is set at build
  time (`scripts/inject-csp-meta.mjs`). `src/lib/site-config.ts` reads each
  `NEXT_PUBLIC_*` via static `process.env.NEXT_PUBLIC_FOO` access so Next.js
  inlines values in the client bundle (dynamic `process.env[name]` is empty in
  the browser and breaks search).
- **SEO:** `buildLocalizedMetadata` (canonical, hreflang). Sitewide
  WebSite + Organization JSON-LD is injected into the exported locale home
  pages at build time (`scripts/inject-structured-data.mjs`, the
  `jsonld:inject` build step); per-activity `Course` JSON-LD and the
  document title are set client-side by `activity-detail-page.tsx` once the
  activity loads (static export cannot pre-render per-activity metadata).
  Optional GTM / Meta Pixel via `NEXT_PUBLIC_GTM_ID` /
  `NEXT_PUBLIC_META_PIXEL_ID` and host allow-lists; CSP `script-src` /
  `connect-src` extended at build time when those env vars are set
  (`scripts/inject-csp-meta.mjs`). `deploy-public-www.yml` and
  `promote-public-www.yml` pass `NEXT_PUBLIC_GTM_ID` /
  `NEXT_PUBLIC_GTM_ALLOWED_HOSTS` from the GitHub Environment. Only the
  GTM container public ID (`GTM-…`) belongs in those vars — GA4 `G-` and
  Google Ads `AW-` IDs stay in the GTM container, not git.
- **Analytics consent:** GTM and the Meta Pixel are consent-gated. The init
  scripts (`public/scripts/init-gtm.js`, `init-meta-pixel.js`) only load the
  vendor scripts when `localStorage` key `siutindei-analytics-consent` is
  `granted`, or after the `siutindei-analytics-consent-granted` window event
  fires. `AnalyticsConsentBanner` (rendered from the root layout) collects
  the decision and links to `/privacy#cookies`. Legal pages (`/privacy`,
  `/terms`) render structured bilingual content from
  `src/content/{en,zh-HK}.json#legal` via
  `src/components/sections/legal-page.tsx`; `docs/legal/README.md` documents
  the update procedure.
- **Data layer (GTM only):** After consent, `src/lib/analytics/data-layer.ts`
  no-ops until `siutindei-analytics-consent=granted`, then
  `window.dataLayer.push({ event, ...params })`. The site does not embed
  extra GA4 or Ads snippets. Events:

  | Event | When | Params |
  |---|---|---|
  | `view_item` | Activity detail listing loaded | `item_id`, `item_name`, `item_brand` (org), `price`, `currency` |
  | `generate_lead` | WhatsApp click | `lead_type`: `whatsapp_activity` / `whatsapp_fab` / `whatsapp_footer`; item fields on the activity CTA |
  | `search` | Search results fetch succeeds | `search_term` / `area_id` / `age` / `category_id` when set |

  Wire-up: `activity-detail-page.tsx`, `whatsapp-fab.tsx`, `footer.tsx`,
  and the search-results success path. GTM fires GA4 (and Ads, once an
  Ads conversion ID/label exists in the container) from these events.

The build is deliberately **gated** by:

| Script | Purpose |
|---|---|
| `assert-build-env-contract.mjs` | Build refuses to run if `NEXT_PUBLIC_SITE_ORIGIN` or `NEXT_PUBLIC_SITE_NAME` is missing. |
| `audit-assets.mjs` | Flags oversized or executable assets in `public/`. |
| `audit:deps:prod` | `npm audit --omit=dev --audit-level=high`. Production deps are
  the gate; GHSA-jmr9-qjv8-65gv (`extract-zip` via `@lhci/cli`) is
  dev-only and has no patched release. `js-yaml` Highs are pinned
  via `overrides` to 3.15.1 / 4.3.1. |
| `inject-static-redirects.mjs` | Injects locale redirect helpers into exported HTML. |
| `inject-html-lang.mjs` | Sets `<html lang>` per locale folder (`en`, `zh-HK`) for crawlers and no-JS. |
| `inject-csp-meta.mjs` | Adds a CSP `<meta http-equiv>` defense-in-depth tag to every exported HTML. |
| `validate-csp-meta.mjs` | Fails the build if any HTML in `out/` is missing the marker. |

## Deployment lifecycle

```
push to main (apps/public_www/**)
        |
        v
deploy-public-www.yml  ── npm ci → assert env → audit → build (with SHA as release id) ──> staging
        |                                                                                     │
        |                                                                                     │
        |                                                            staging bucket
        |                                                            ├── *.html, _next/static/*, …
        |                                                            └── releases/<sha>/<full export>
        |                                                            └── releases/latest-release-id.txt
        |
        v
workflow_dispatch (Promote Public Website Release)
        ├── promotion_mode=latest_staging  → reads marker, S3-copy + invalidate (default)
        ├── promotion_mode=release_id      → operator supplies sha, fresh prod build then deploy
        └── promotion_mode=maintenance_on  → upload apps/public_www/maintenance/ to production
```

### Workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| [`deploy-backend.yml`](../../.github/workflows/deploy-backend.yml) | `workflow_dispatch` (`public website` or `all stacks`), `push: backend/**` | CDK deploy of `lxsoftware-siutindei-public-www` (S3 + CloudFront for production and staging). |
| [`deploy-public-www.yml`](../../.github/workflows/deploy-public-www.yml) | `push: main`, `workflow_dispatch`, `repository_dispatch: deploy-public-www` | Build + sync to staging bucket, write release marker, then run the staging smoke checks against the deployed site. |
| [`promote-public-www.yml`](../../.github/workflows/promote-public-www.yml) | `workflow_dispatch` | Promote a staging release to production or flip production into maintenance mode. |
| [`smoke-public-www-staging.yml`](../../.github/workflows/smoke-public-www-staging.yml) | `workflow_dispatch` | Crawl staging sitemap and assert every page responds 2xx/3xx. |
| [`lighthouse-public-www.yml`](../../.github/workflows/lighthouse-public-www.yml) | `workflow_dispatch` | Run Lighthouse CI on the production build. |

### Promotion script

The deploy script lives at
[`scripts/deploy/deploy-public-www.sh`](../../scripts/deploy/deploy-public-www.sh)
and is invoked by both workflows. It supports three primary modes:

1. **Standard deploy**: `PUBLIC_WWW_ENVIRONMENT=staging|production` syncs
   `apps/public_www/out` to the bucket, writes a release marker, and
   invalidates CloudFront with a site-scope path list (locale prefixes
   `/en*` and `/zh-HK*`, exported pages, `/_next/static/*`,
   `/fixtures/*`, and `/v1/activities/search*`). Promotion and
   maintenance still invalidate `/*`.
2. **Promotion**: when `PUBLIC_WWW_PROMOTE_RELEASE_ID` is set:
   - if `PUBLIC_WWW_PROMOTION_BUILD_DIR` is also set, the local build (with
     production env vars) is uploaded to production;
   - otherwise the script does an S3-side `aws s3 sync` from
     `s3://staging/releases/<id>/` to `s3://production/`.
3. **Maintenance mode**: `PUBLIC_WWW_MAINTENANCE_MODE=true` uploads
   `apps/public_www/maintenance/` to the target bucket with `Cache-Control:
   no-store`, after substituting `__NEXT_PUBLIC_EMAIL__`,
   `__NEXT_PUBLIC_WHATSAPP_URL__`, `__NEXT_PUBLIC_INSTAGRAM_URL__` placeholders.

The script also enforces `robots.txt: User-agent: *\nDisallow: /` whenever
the target environment is `staging`.

CloudFront is the only edge cache on the CloudFront aliases
(`siutindei.com` / `siutindei-www-staging`). Those records CNAME directly
to CloudFront (DNS-only / grey cloud). `www.siutindei.com` and
`siutindei-www.lx-software.com` are Cloudflare-proxied 301s to the apex.
Standard deploys do not invalidate `/*` so they stay under CloudFront's
15-wildcard-in-progress
cap. The site-scope list is aligned with evolvesprouts and adapted to
this site's locales, pages, staging search fixture, and search-API
proxy. HTML objects still carry `Cache-Control: public, max-age=300,
must-revalidate`, so browsers may keep a page for up to five minutes
after the CloudFront invalidation.

## Security headers and CSP

The CloudFront response headers policy applies in front of every viewer
response. The HTML produced by `next build` *also* carries an inline CSP
`<meta http-equiv>` tag (`scripts/inject-csp-meta.mjs`) so that CSP applies
even when an HTML file is rendered outside CloudFront (local QA, opened
from disk, archived snapshot).

The HTML meta CSP baseline (see `scripts/inject-csp-meta.mjs`) is:

```
default-src 'self'; img-src 'self' data: https:; style-src 'self';
script-src 'self' 'sha256-…' …; font-src 'self' data:; connect-src 'self';
base-uri 'self'; object-src 'none'; frame-ancestors 'none';
```

Styles load from external stylesheets (`/_next/static/chunks/*.css` and
`globals.css`); the app forbids JSX `style={...}` attributes. Scroll lock
and the optional staging badge use CSS classes instead of JS-assigned
inline styles so `style-src` does not need `'unsafe-inline'`.
Next.js static export embeds required inline flight/hydration scripts; the
build collects a `sha256-` hash for each unique inline script body across
`out/**/*.html` and adds those hashes to `script-src` so React can hydrate
without allowing arbitrary inline script. Ad-hoc inline scripts and inline
event handlers remain disallowed via the `.cursorrules` "no
`dangerouslySetInnerHTML`, no `eval`" rule.

CloudFront’s response headers policy applies a smaller CSP fragment
(`base-uri`, `object-src`, `frame-ancestors` only); the meta tag carries
the full policy above.

## Search API edge caching

The public website's activity-search calls are proxied and cached at the
CloudFront edge instead of paying for an API Gateway stage cache cluster
(a fixed hourly charge that dominated the API Gateway bill). Both website
distributions (production + staging) carry an extra cache behavior:

| Item | Value |
|---|---|
| Path pattern | `/v1/activities/search` (exact path; admin/other API paths are **not** exposed) |
| Origin | `HttpOrigin` → API Gateway custom domain from the `SearchApiProxyOriginDomain` parameter (`siutindei-api.lx-software.com`), HTTPS-only, TLS 1.2+ |
| Allowed methods | `GET`, `HEAD`, `OPTIONS` |
| Allow-list function | `${env}SearchProxyAllowlistFunction` CloudFront Function (viewer-request) returns `405` for any other method |
| Cache policy (`SearchApiCachePolicy`) | TTL min `0` / default `300s` / max `300s`; cache key = **all query strings**, **no** headers, **no** cookies (a single cached entry is shared across all callers) |
| Origin-request policy (`SearchApiOriginRequestPolicy`) | Forwards all query strings + `x-api-key`, `x-device-attestation`, `Accept` headers to the origin on a cache **miss** |

CloudFront Function creation is serialized across both environments via an
`addDependency` chain (prod path-rewrite → prod search-proxy → shared
listing-events allow-list → staging path-rewrite → staging search-proxy)
so a single deploy does not breach the regional CloudFront Functions API
rate limit.

## Listing-event ingest (first-party funnel)

Public www also posts consented `search` / `view_item` / `generate_lead`
events to **`POST /v1/listing-events`** so Aurora can feed
`listing_events_daily` / `v_funnel_daily`. The Executive Board already
reads GA4 via its `web` tools; this path is location-grained product
telemetry, not a GA4 pull.

| Item | Value |
|---|---|
| Path pattern | `/v1/listing-events` (exact path) |
| Origin | Same API Gateway custom domain as search |
| Allowed methods | CloudFront `ALLOW_ALL`, allow-list function permits `POST` / `OPTIONS` only |
| Cache | `CACHING_DISABLED` |
| Origin-request policy | Forwards `x-api-key`, `x-device-attestation`, `Accept`, `Content-Type`, `Origin`; no query strings |
| Auth | Same public search API key + static device-attestation token |
| Consent | Same `siutindei-analytics-consent` gate as the GTM data layer |

`NEXT_PUBLIC_SEARCH_API_BASE_URL` must be the website origin so ingest is
same-origin (`connect-src 'self'`). Staging fixture mode does not post.

To route traffic through the edge cache, the website build must point
`NEXT_PUBLIC_SEARCH_API_BASE_URL` at the website's own origin (e.g.
`https://siutindei.com`) rather than directly at
`siutindei-api.lx-software.com`; `src/lib/activities/search-client.ts`
resolves `new URL('/v1/activities/search', base)`, which then hits this
behavior same-origin. With same-origin requests the CSP `connect-src 'self'`
already covers the call (no API host needs to be added to CSP).

**Security/behavioral note:** on a cache **hit** CloudFront serves the cached
response without re-invoking the origin, so the per-request `x-api-key` /
`x-device-attestation` checks (anti-abuse controls, not data protection) are
not enforced for cached entries. This matches the intent of a *public* search
endpoint and the prior API Gateway method-cache behavior of returning cached
results; abuse protection at the edge is provided by the CloudFront WAF
WebACL. Only the exact `/v1/activities/search` path is proxied, so admin
endpoints (`/v1/admin/*`) are never reachable through the website domain.
Distribution-level custom error responses (403/404 → `/404.html`) still apply
to this behavior; validate API error handling on staging before pointing
production traffic at the edge.
