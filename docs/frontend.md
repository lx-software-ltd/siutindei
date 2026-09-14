# Frontend integration

This document describes how Siu Tin Dei front-end applications integrate with
the backend, share configuration, and stay within the
[performance target](architecture/performance.md) (search interactive with
**~100 listings** in under **2 seconds**).

## Applications

| App | Directory | Delivery | Primary backend use |
|---|---|---|---|
| Public website | `apps/public_www/` | Static export → S3 + CloudFront | Public search, listing events, optional Google Maps |
| Admin console | `apps/admin_web/` | Next.js (Amplify hosting) | Cognito auth + admin/manager CRUD APIs |
| Mobile | `apps/siutindei_app/` | Flutter (Play / App Store) | Cognito + public search with attestation |

Shared UI packages: `packages/flutter_ui/`, `packages/react_ui/` (Storybook).

## Public website (`apps/public_www`)

### Architecture constraints

- **Static export only** (`output: 'export'`) — no server components that fetch
  per request; activity detail metadata is applied client-side after load.
- **Security / CSP:** No `dangerouslySetInnerHTML`, no inline `style={…}`, SVGs
  in `public/images/`, env-specific values only via
  `src/lib/site-config.ts`.
- **Tests** live under `apps/public_www/tests/`, not beside components in
  `src/`.

Page structure mirrors the evolvesprouts layout:

- `src/components/pages/` — route-level composition
- `src/components/sections/` — marketing and search sections
- `src/components/shared/` — primitives (nav, consent, analytics helpers)
- `src/app/[locale]/` — App Router entries per locale (`en`, `zh-HK`)

See [`architecture/public-www.md`](architecture/public-www.md) for hosting,
CSP injection, and deploy lifecycle.

### Backend integration (search)

**Config:** `getSearchConfig()` in `src/lib/site-config.ts` exposes staging
fixture mode, API base URL, API key, and attestation token.

**API calls:** `src/lib/activities/search-client.ts`

```text
getSearchConfig()
  → staging? fetchStagingActivitySearch()
  → else fetch(/v1/activities/search?...)
```

Query parameters align with [`docs/api/search.yaml`](api/search.yaml). Default
`limit` is 50; search results may request up to 200 for client-side `q`
filtering—tune down when approaching the 100-listing perf goal.

**Filters:** URL state (`age`, `region`, `types`, `q`, `view`) is parsed in
`search-params.ts` and converted to API params in `filtersToApiParams`.

**Detail:** `fetchActivityListingById` reuses search with `activity_id` and
`limit: 1`, with `priority: 'high'` on the fetch.

### Backend integration (analytics)

- **GTM data layer:** `src/lib/analytics/data-layer.ts` (consent-gated).
- **First-party ingest:** `src/lib/analytics/listing-events-ingest.ts` POSTs to
  `/v1/listing-events` when not in staging-fixture mode.

### Performance techniques (100 listings)

| Technique | Location | Effect |
|---|---|---|
| Same-origin API URL | Build env + `search-client.ts` | CloudFront edge cache, simpler CSP |
| `fetch` priority | `search-client.ts` (`highPriority`) | Faster detail hydration |
| Lazy images + fetchPriority | `listing-card.tsx`, `listing-image.ts` | Limits bandwidth for off-screen cards |
| Deferred card render (index ≥ 4) | `listing-grid.tsx`, `listing-image.ts` | Reduces initial main-thread work |
| Fixed image dimensions | `LISTING_IMAGE_WIDTH` / `HEIGHT` | Low CLS |
| Parallel map load | `search-results-page.tsx` + map components | Maps script does not gate search fetch |
| Skeleton grid | `listing-grid.tsx` | Perceived performance while JSON loads |
| Static asset audit | `audit-assets.mjs` | Blocks huge files in `public/` |

**Measurement:** `npm run build` then Lighthouse via
`apps/public_www/.lighthouserc.json` (performance score ≥ 0.9). Throttle CPU/network
in DevTools when validating the 2 s / 100-row scenario.

**Local dev:**

```bash
cd apps/public_www
NEXT_PUBLIC_SITE_ORIGIN=http://localhost:3000 \
NEXT_PUBLIC_SITE_NAME="Siu Tin Dei" \
npm run dev
```

For search without a live API, enable staging fixture flags documented in
[`backend.md`](backend.md).

### Home discovery

`discovery-home-section.tsx` loads carousel slices via `fetchActivitySearch` with
small limits per category—keep limits modest to protect home LCP.

## Admin console (`apps/admin_web`)

### Backend integration

- **Config:** `apps/admin_web/src/lib/config.ts` validates
  `NEXT_PUBLIC_API_BASE_URL` and Cognito variables at startup.
- **API client:** Generated from `docs/api/admin.yaml` (`npm run generate:api`).
- **Auth:** Cognito hosted UI; tokens attached to admin API requests (see app
  auth modules under `src/` — do not bypass for production).

### Performance notes

- Prefer **cursor pagination** on list screens (organizations, activities,
  users) instead of loading entire tables.
- Run `npm run lint` and `npm run typecheck` before merge; E2E lives in
  `apps/admin_web/e2e/` when UI flows change.

Deploy and env details: [`deployment/admin-web.md`](deployment/admin-web.md).

## Mobile app (`apps/siutindei_app`)

- **MVVM + Riverpod** under `lib/viewmodels` and `lib/views`.
- **API:** `packages/api_client_dart` generated from OpenAPI.
- **Search:** Same `/v1/activities/search` contract; use cursor pagination for
  long result sets.
- **Attestation:** Firebase App Check tokens for device attestation header.

App-specific docs: `apps/siutindei_app/docs/getting-started.md`.

## Cross-cutting practices

### Environment variables

| Surface | Pattern |
|---|---|
| Public www | `NEXT_PUBLIC_*` inlined at build; read only via `site-config.ts` |
| Admin web | `NEXT_PUBLIC_*` for API + Cognito |
| Flutter | `--dart-define` for API base and Amplify config |

Never read secrets from git; use CI environment configuration.

### OpenAPI workflow

1. Change `docs/api/*.yaml`.
2. Regenerate TS/Dart clients (`scripts/codegen/`).
3. Update consuming app calls and tests.

### When UI changes affect performance

1. Re-check [performance checklist](architecture/performance.md#optimization-checklist-release).
2. Update Playwright tests under `apps/admin_web/e2e` for admin flows.
3. Update Vitest tests under `apps/public_www/tests` for search/listing UI.

## Related documentation

- [`backend.md`](backend.md) — API auth, search parameters, edge cache
- [`architecture/performance.md`](architecture/performance.md) — targets and metrics
- [`architecture/public-www.md`](architecture/public-www.md) — static site design
- [`api/search.yaml`](api/search.yaml) — public search contract
