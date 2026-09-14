# Performance

This document defines performance targets, metrics, and tuning guidance for
Siu Tin Dei client surfaces—especially the public website search experience
with large result sets. It complements hosting and API-edge design in
[`public-www.md`](public-www.md) and optional Cloudflare strategies in
[`cloudflare-optimization.md`](cloudflare-optimization.md).

## Product target

**Goal:** On a typical broadband connection (desktop and mobile), a user
opening search with **~100 activity listings** should reach an **interactive
results view within 2 seconds** from navigation start.

Interpret “loads” as:

| Phase | What “done” means |
|---|---|
| Document | HTML + critical CSS/JS delivered (static export from S3/CloudFront). |
| Data | First search `fetch` completes and JSON is parsed (up to 100 items in one response, or fewer with client-side text filter). |
| UI | Listing grid or map split shows real cards (skeletons replaced); main thread is not blocked long enough to miss interaction budget. |

The **2 second** budget is an engineering target for staging validation and
regression checks—not a contractual SLA. Production should still meet
Lighthouse CI thresholds (see below).

## Scope and non-goals

- **In scope:** `apps/public_www` search and discovery, public
  `/v1/activities/search`, CloudFront edge cache on the website origin,
  listing images and optional Google Maps.
- **Out of scope here:** Admin console latency, mobile Flutter cold start,
  Aurora capacity planning (see [`aws-assets-map.md`](aws-assets-map.md)
  alarms), and payment flows.

Endpoint request/response shapes live only in
[`docs/api/search.yaml`](../api/search.yaml).

## Performance metrics

### Core Web Vitals (field)

Track in GTM/GA4 (after consent) or Real User Monitoring when available:

| Metric | Target (search with 100 listings) | Notes |
|---|---|---|
| **LCP** | &lt; 2.5 s (good) | Often driven by first listing image or map tile; keep hero/list above-the-fold lean on search routes. |
| **INP** | &lt; 200 ms (good) | Map pin selection and filter chips must stay responsive; avoid large synchronous JSON transforms. |
| **CLS** | &lt; 0.1 | Listing cards use fixed 4:3 dimensions (`LISTING_IMAGE_WIDTH` / `HEIGHT` in `listing-image.ts`). |

### Lab (CI)

| Check | Location | Threshold |
|---|---|---|
| Lighthouse **performance** | `apps/public_www/.lighthouserc.json` | Score ≥ **0.9** (category assertion) |
| Lighthouse accessibility / SEO / best practices | Same | Score ≥ **0.9** |
| Workflow | `lighthouse-public-www.yml` | Run against production build (`out/`) |

### API and edge

| Signal | Where | What to watch |
|---|---|---|
| Search latency (p99) | CloudWatch (search Lambda / API Gateway) | Spikes when `limit` is high or DB filters miss indexes |
| CloudFront cache hit ratio | Distribution metrics for `/v1/activities/search` | Higher hit ratio → lower TTFB for repeat filter combinations |
| Origin 5xx / throttles | API Gateway + Lambda alarms | Failures block “interactive” even if static shell is fast |

### Custom timings (optional)

In browser DevTools → Performance, mark:

1. `navigationStart` → `responseEnd` for document.
2. `fetchStart` → `responseEnd` for `/v1/activities/search` or staging fixture.
3. First paint of listing card content (not skeleton).

Budget for **100 listings** (indicative, lab Wi‑Fi):

| Segment | Budget |
|---|---|
| HTML + JS (cached `_next/static`) | &lt; 400 ms |
| Search JSON (≤100 items, gzip) | &lt; 600 ms TTFB + download on cache miss; &lt; 150 ms on edge hit |
| Parse + React render (100 cards, deferred below fold) | &lt; 400 ms |
| Maps script (parallel, map view only) | Must not block first paint of list column |

## Architecture levers

### Static shell (public website)

- Next.js **`output: 'export'`** — no SSR per request; HTML is cached at
  CloudFront with short browser `max-age` (see [`public-www.md`](public-www.md)).
- Build gates: asset audit, CSP inject/validate, env contract — prevent
  shipping oversized or misconfigured bundles.

### Same-origin search + edge cache

Production should set `NEXT_PUBLIC_SEARCH_API_BASE_URL` to the **site origin**
(e.g. `https://siutindei.com`) so `fetch('/v1/activities/search', …)` hits
CloudFront’s dedicated behavior (5-minute TTL, query-string cache key).
Direct calls to the API Gateway hostname bypass that cache and add CSP
`connect-src` complexity.

See **Search API edge caching** in [`public-www.md`](public-www.md).

### Staging fixture mode

When `NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED=true`, listings load from
`/fixtures/activity_search_staging.json` on the same origin—useful for UI perf
tests without Aurora. Production promote sets this to `false`.

## Backend tuning (search)

Guidelines for keeping **100-listing** responses fast; details in
[`docs/backend.md`](../backend.md).

1. **Page size:** `limit` is 1–200 (default 50). For the 100-listing target,
   prefer a single `limit=100` (or two cursor pages of 50) instead of many
   round trips. Avoid `limit=200` unless filters already shrink the set.
2. **Payload shape:** Return only fields the OpenAPI schema requires; omit
   large unused blobs from list responses. Keep translation maps compact.
3. **Database:** Ensure filters (`age`, `area_id`, `category_id`, cursor
   ordering) use indexed paths documented in
   [`database-schema.md`](database-schema.md). Slow queries dominate cache-miss
   latency.
4. **Compression:** API Gateway + CloudFront should serve `gzip`/`br` JSON;
   verify response sizes in staging (aim for well under 500 KB for 100 items).
5. **Cold starts:** Keep search Lambda bundles lean; watch p99 duration alarms.
6. **Caching semantics:** Edge cache is shared per URL (all query params in the
   key). TTL 300 s — acceptable for public catalog data; not for personalized
   admin data.

## Frontend tuning (public website)

See [`docs/frontend.md`](../frontend.md) for integration patterns. Highlights
for **100 listings**:

1. **Fetch priority:** Activity detail uses `fetch(..., { priority: 'high' })`
   in `search-client.ts`; search results use default priority unless UX requires
   otherwise.
2. **Images:** Carousel eager-loads first two cards; grid uses lazy loading
   with `decoding="async"` and deferred card render for index ≥ 4
   (`shouldDeferListingCardRender`).
3. **Maps:** Map script loads in parallel with search fetch on map view; do not
   await Maps before starting search.
4. **Client text filter:** `q` filtering runs in the browser after API fetch—
   request enough rows from the API that filtered results still reach UX
   expectations without extra round trips.
5. **No virtualized list today:** 100 DOM cards are acceptable with defer +
   lazy images; beyond ~150 consider virtualization or stricter `limit`.
6. **Analytics:** Listing-event ingest is consent-gated and async; it must not
   block rendering.

## Optimization checklist (release)

Before promoting public www or shipping search API changes:

- [ ] Staging search with `limit=100` (or fixture with ≥100 rows): DevTools
      network waterfall under 2 s to interactive grid on throttled “Fast 4G”.
- [ ] CloudFront cache hit on second identical search (edge HIT).
- [ ] Lighthouse CI performance ≥ 0.9 on home and search list view.
- [ ] No regression in `audit-assets.mjs` (oversized `public/` files).
- [ ] `NEXT_PUBLIC_SEARCH_API_BASE_URL` points at site origin in production
      build env.
- [ ] CloudWatch search p99 and 5xx within normal bounds after deploy.

## Related documentation

- [`docs/backend.md`](../backend.md) — API integration and search contracts
- [`docs/frontend.md`](../frontend.md) — client apps and env configuration
- [`public-www.md`](public-www.md) — hosting, CSP, edge proxy behaviors
- [`overview.md`](overview.md) — system diagram and caching summary
- [`docs/api/search.yaml`](../api/search.yaml) — search parameters and schemas
