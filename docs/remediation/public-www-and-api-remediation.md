# Remediation Plan — Public Website (`apps/public_www`) & Search API

**Audience:** Junior developer executing fixes one item at a time.
**Status:** Draft for review. No code changes have been made; this is a worklist.
**Scope:** The public marketing/discovery site (`apps/public_www`) and the public
search API path it depends on (`backend/src/app/api/search.py`, the API Gateway
config in `backend/infrastructure/lib/api-stack.ts`, and the CI deploy/promote
workflows).

## How to use this document

- Work top-down: **P0 (critical) → P1 (high) → P2 (medium) → P3 (low)**.
- Each task has: **Problem / Why it matters / Where / Fix steps / How to verify**.
- Do **one task per branch/PR**. Branch name pattern: `cursor/<short-desc>`.
- Follow the repo rules in `.cursorrules` and `AGENTS.md` (plan → approval →
  execute). For Python commits run `pre-commit run ruff-format --all-files`
  first.
- Before committing, run the relevant checks from `AGENTS.md`
  ("Lint / test / build").

### Standard verification commands (copy/paste)

```bash
export NVM_DIR="/home/ubuntu/.nvm" && . "$NVM_DIR/nvm.sh"

# Public website
cd apps/public_www && npm ci && npm run lint && npm run typecheck && npm test

# Public website production build (requires env contract)
cd apps/public_www \
  && NEXT_PUBLIC_SITE_ORIGIN=http://localhost:3000 \
     NEXT_PUBLIC_SITE_NAME="Siu Tin Dei" \
     npm run build

# CDK infrastructure
cd backend/infrastructure && npm ci && npm run lint && npm run build

# Backend
pre-commit run --all-files
PYTHONPATH=backend/src \
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/backend_test \
  python3 -m pytest tests backend -q
```

---

## P0 — Critical (production-breaking)

### P0-1. Production build ships with no Search API configuration → live search is broken

**Status: RESOLVED.** `promote-public-www.yml` passes
`NEXT_PUBLIC_SEARCH_API_BASE_URL` (production Environment var),
`NEXT_PUBLIC_SEARCH_API_KEY`, and `CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN`
(as `NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN`) to both the env-contract check
and the build. `assert-build-env-contract.mjs` hard-fails when they are
missing with `NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED=false`. That token is
a static website credential, not a Firebase App Check JWT. The device
attestation authorizer accepts it only with the CloudFront-injected
`X-Origin-Verify` secret (`CDK_PARAM_PUBLIC_WWW_ORIGIN_VERIFY`). Operator
steps live in `docs/deployment/launch-checklist.md`.

**Problem.** The production promote workflow builds the site with
`NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED: 'false'` but never passes
`NEXT_PUBLIC_SEARCH_API_BASE_URL`, `NEXT_PUBLIC_SEARCH_API_KEY`, or
`NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN`. Because Next.js inlines `NEXT_PUBLIC_*`
at build time, the deployed bundle has an empty `apiBaseUrl`.

**Why it matters.** At runtime `fetchActivitySearch()` throws
`"Search API is not configured."`, so search and the activity-detail page fail
in production. The CSP injector also won't add the API origin to `connect-src`,
so even a correctly configured base URL would be blocked.

**Where.**
- `.github/workflows/promote-public-www.yml` build `env:` block (around lines
  124–134) — missing the search vars.
- `.github/workflows/deploy-public-www.yml` build `env:` block (around lines
  76–88) — staging path only works because it uses the fixture.
- `apps/public_www/src/lib/activities/search-client.ts:119-121` — the throw.
- `apps/public_www/scripts/inject-csp-meta.mjs` — `connect-src` derives from
  `NEXT_PUBLIC_SEARCH_API_BASE_URL`.

**Fix steps.**
1. Decide where the production search API base URL, API key, and attestation
   token come from. Prefer GitHub **Environment variables/secrets** on the
   `production` environment, or resolve them in
   `scripts/deploy/resolve-public-www-build-env.sh` from CloudFormation outputs
   (same pattern already used for `production_site_origin`). **Do not** hardcode
   values (`.cursorrules` security rule). The API key/attestation token are
   sensitive — store them as **secrets**, not plain vars.
2. Add the three vars to the build `env:` block in
   `promote-public-www.yml` (and confirm the staging
   `deploy-public-www.yml` path is correct — staging may legitimately rely on
   the fixture and not need them).
3. Verify the CSP injector adds the API origin to `connect-src` once the base
   URL is present.

**How to verify.**
- Run a production-style build locally with the vars set and inspect
  `apps/public_www/out/**/*.html` for a CSP `<meta>` whose `connect-src`
  includes the API origin.
- Grep the built JS bundle for the API base URL to confirm it was inlined.
- Manual: serve `out/` and confirm a search request hits the configured API.

---

### P0-2. API Gateway response cache can return the wrong activity/category results

**Status: RESOLVED.** `cacheKeyParameters` now includes `activity_id` and
`category_id` and the stale keys (`day_of_month`, `start_at_utc`,
`end_at_utc`) are gone. The API Gateway stage cache cluster is disabled
entirely; response caching moved to the CloudFront edge, whose
`SearchApiCachePolicy` uses `CacheQueryStringBehavior.all()`, so every query
parameter is part of the cache key.

**Problem.** Search has API Gateway caching enabled (`cacheClusterEnabled: true`,
`cachingEnabled: true`, 5-minute TTL). The cache-key parameter list does **not**
include `activity_id` or `category_id`, but the handler supports both.

**Why it matters.** Two requests that differ only by `activity_id` (or
`category_id`) share the same cache entry. The activity-detail page calls
`fetchActivityListingById()` → `?activity_id=...`; users can be served a cached
response for a **different** activity. This is a correctness/data-integrity bug.

**Where.**
- `backend/infrastructure/lib/api-stack.ts:1965-1981` — `cacheKeyParameters`
  list (no `activity_id`, no `category_id`).
- `backend/infrastructure/lib/api-stack.ts:1833-1839` — caching enabled.
- `backend/src/app/api/search.py:99-106` — handler reads `activity_id` and
  `category_id`.

**Fix steps.**
1. Add to `cacheKeyParameters`:
   - `method.request.querystring.activity_id`
   - `method.request.querystring.category_id`
2. Keep them in `requestParameters` (the loop already maps each to `false`).
3. **Also remove the stale keys** that the handler/OpenAPI do not implement
   (see P2-1): `day_of_month`, `start_at_utc`, `end_at_utc`. Coordinate so this
   is a single coherent cache-key change.

**How to verify.**
- `cd backend/infrastructure && npm run build` (CDK synth/compile passes).
- `npx cdk synth` and inspect the synthesized `AWS::ApiGateway::Method` for the
  search resource — confirm `cacheKeyParameters` lists `activity_id` and
  `category_id`.
- Post-deploy (if possible): two `curl`s with same filters but different
  `activity_id` must return different bodies (and `X-Cache`/age behavior should
  differ per key).

---

## P1 — High

### P1-1. In-VPC Lambdas call Cognito directly instead of the AWS proxy

**Problem.** `admin_bootstrap` and the migration `seed` call Cognito IDP
directly via `get_cognito_idp_client()` / `boto3.client("cognito-idp")`. Both
run **in-VPC** (no `noVpc: true`). The VPC is created with `natGateways: 0` and
there is **no Cognito-IDP interface endpoint** (Cognito PrivateLink is blocked
by ManagedLogin — see `.cursorrules`).

**Why it matters.** With no NAT and no Cognito endpoint, these calls can hang
until timeout and fail. The architecture rule is explicit: in-VPC Lambdas must
use `app.services.aws_proxy.invoke()` for Cognito (the admin API already does
this correctly in `admin_cognito.py`).

**Where.**
- `backend/lambda/admin_bootstrap/handler.py:55` (`get_cognito_idp_client()`).
- `backend/db/migrations/.../seed.py:43` and migration
  `0005_add_organization_owner.py:45`.
- CDK: `backend/infrastructure/lib/api-stack.ts:2294` (`adminBootstrapFunction`)
  and `:1377` (`migrationFunction`) — neither sets `noVpc: true`.
- Correct pattern reference: `backend/src/app/api/admin_cognito.py:45`.

**Fix steps (pick one approach per function, confirm with reviewer first).**
- **Option A (preferred, matches rule):** Route Cognito calls through
  `app.services.aws_proxy.invoke()` so the out-of-VPC proxy Lambda performs the
  Cognito operation.
- **Option B:** If a function legitimately needs no VPC resources, set
  `noVpc: true` on its CDK definition (as done for `awsProxyFunction`,
  `postAuthFunction`, authorizers) so it has internet egress. Confirm it does
  **not** need DB/VPC access first.
- Add/extend unit coverage to assert the proxy is used (mock
  `aws_proxy.invoke`).

**How to verify.**
- `cd backend/infrastructure && npm run build`.
- Backend tests pass.
- If deployable: trigger bootstrap/migration and confirm Cognito ops succeed
  (CloudWatch logs show proxy invocation, not a network timeout).

> Note: A related earlier concern about `create_auth_challenge` calling **SES**
> directly in-VPC is **not** a defect — the VPC has an SES interface endpoint
> (`api-stack.ts:204`), so that path works. Do not change it.

---

### P1-2. Inline `<svg>` markup in a TSX component (rule violation) + dead code

**Status: RESOLVED.** `search-map-panel.tsx` has been deleted; no
`SearchMapPanel` references remain.

**Problem.** `SearchMapPanel` renders inline `<svg>`/`<circle>` markup in TSX,
which `.cursorrules` forbids for `apps/public_www/**` ("inline `<svg>...</svg>`
markup in TSX components"). The component is also **dead code** — it is exported
but never imported (the map view uses `ActivityGoogleMap`).

**Why it matters.** Rule violation that will (or should) fail review, plus the
SVG uses poor a11y patterns (`role="button"` on `<circle>`). Dead code adds
maintenance cost and confusion.

**Where.** `apps/public_www/src/components/sections/search/search-map-panel.tsx`
(inline `<svg>` at lines 69–104; whole file unused).

**Fix steps.**
1. Confirm it is unused: grep the repo for `SearchMapPanel` imports.
2. **Preferred:** delete the file (and its test if any).
3. If it must stay, move the SVG to `apps/public_www/public/images/` and
   reference it via `/images/...`, and fix the a11y (use real `<button>`
   elements, not clickable `<circle>`).

**How to verify.**
- `npm run lint && npm run typecheck && npm test` in `apps/public_www`.
- Grep confirms no remaining references.

---

### P1-3. Activity-detail pages have generic, client-rendered metadata (SEO)

**Status: RESOLVED (option 1).** The detail page injects per-activity
`Course` JSON-LD and updates `document.title` client-side once the activity
loads; sitewide WebSite + Organization JSON-LD is injected into the locale
home pages at build time (`scripts/inject-structured-data.mjs`). Option 2
(pre-generating static activity pages via `generateStaticParams`) remains a
future enhancement once the activity set is stable and enumerable at build
time.

**Problem.** `/[locale]/activity/?id=...` uses a static generic title; the real
activity name/description is fetched client-side after load.

**Why it matters.** Crawlers and social-share unfurlers see generic metadata for
every activity → poor SEO and bad link previews. This is the main
discovery-surface page.

**Where.**
- `apps/public_www/src/app/[locale]/activity/page.tsx:17-31` (generic
  `generateMetadata`).
- `apps/public_www/src/components/pages/activity-detail-page.tsx` (client fetch).

**Fix steps (discuss approach before coding — this touches static-export
constraints).** Options, easiest first:
1. **Lowest effort:** improve the generic metadata and add JSON-LD
   (`Event`/`Course`) injected client-side; documents intent but limited SEO
   gain.
2. **Better:** if the activity set is enumerable at build time, pre-generate
   static activity pages (`generateStaticParams`) so each has real metadata.
   This is a larger change and must respect `output: 'export'`.
3. Add an `aria-live` region for the loading state on the detail page
   (`activity-detail-page.tsx:111-116`).

**How to verify.**
- Build and inspect generated HTML `<head>` for per-activity title/description
  (if static generation is chosen).
- Manual: share/preview a couple of activity URLs.

---

## P2 — Medium

### P2-1. Stale/undocumented search query parameters across CDK, OpenAPI, and Flutter

**Status: RESOLVED.** The stale CDK cache keys were removed with P0-2, and
`ActivitySearchFilters` in the Flutter app now carries only parameters the
search API implements (`day_of_month`/`start_at_utc`/`end_at_utc` remain
only as response-schedule fields, which is correct).

**Problem.** Several params are referenced in places but **not** implemented in
the search handler or OpenAPI: `day_of_month`, `start_at_utc`, `end_at_utc`
(in CDK cache keys), and `searchQuery`/`day_of_month`/`start_at_utc`/`end_at_utc`
(in the Flutter `ActivitySearchFilters`).

**Why it matters.** Drift between client, CDK, and the actual API surface causes
confusion and dead config. Ties into the cache-key fix (P0-2).

**Where.**
- `backend/infrastructure/lib/api-stack.ts:1973-1977` (stale cache keys).
- `apps/siutindei_app/lib/models/activity_models.dart:152-156` (params the API
  doesn't accept).
- Source of truth for supported params: `backend/src/app/api/search.py:91-120`
  and `docs/api/search.yaml`.

**Fix steps.**
1. Remove stale cache-key entries in CDK (do with P0-2).
2. Remove unsupported params from the Flutter model, or open a follow-up if the
   product intends to add them server-side.
3. Confirm `docs/api/search.yaml` lists exactly the supported params.

**How to verify.** CDK build; Flutter `flutter analyze` (when SDK available);
diff query params between code, OpenAPI, and clients.

---

### P2-2. Search input validation is weaker than the OpenAPI contract

**Problem.** OpenAPI documents ranges (age ≥ 0, day 0–6, minutes 0–1439,
limit 1–200) and the parser only does `int()`/`Decimal()`/`UUID()`. Invalid
values (negative age, out-of-range day, `price_min > price_max`) yield generic
400s instead of structured validation errors; language codes are not validated
against the enum.

**Why it matters.** Inconsistent error responses, weaker contract enforcement.
No SQL-injection risk (ORM is parameterized), so this is correctness/robustness,
not security-critical.

**Where.**
- `backend/src/app/api/search.py:91-120`.
- `backend/src/app/api/parsers.py:18-32`, `:105-122`.
- Compare admin language validation `_validate_language_code` for the pattern.

**Fix steps.**
1. Add bounds checks in the parsers (raise `ValidationError` with a clear
   message and 400 status, matching the existing `ValidationError` path).
2. Add a `price_min <= price_max` check.
3. Validate language codes against the allowed set (reuse admin helper).
4. Add unit tests for each rejected case.

**How to verify.** Backend tests; add cases to `tests/test_search_*.py`.

---

### P2-3. Build env contract enforces only 2 variables (rule violation)

**Status: RESOLVED.** `assert-build-env-contract.mjs` now enumerates the
full `NEXT_PUBLIC_*` surface: hard-required core vars, search vars required
whenever the staging fixture is disabled, warn-level recommended vars, and
an optional list whose set/unset status is logged per run. `.env.example`
documents every variable.

**Problem.** `.cursorrules` requires `assert-build-env-contract.mjs` to list
**every** `NEXT_PUBLIC_*` the static export depends on. It currently enforces
only `NEXT_PUBLIC_SITE_ORIGIN` and `NEXT_PUBLIC_SITE_NAME`.

**Why it matters.** Misconfigured deploys (e.g. P0-1) pass the contract check
silently. The contract is supposed to be the guardrail.

**Where.**
- `apps/public_www/scripts/assert-build-env-contract.mjs:9`.
- Keep in sync with `.env.example`, `resolve-public-www-build-env.sh`, and the
  workflow `env:` blocks (per the file's own header comment).

**Fix steps.**
1. Expand `REQUIRED` to include the vars the build genuinely depends on.
   Be careful: some vars are environment-specific (staging-only fixture vars,
   optional analytics IDs). Distinguish **required-everywhere** vs
   **optional/conditional**; only hard-fail on the truly required set, and warn
   on recommended ones — or split into two lists.
2. Update `.env.example` to document **all** vars, including the currently
   missing `NEXT_PUBLIC_SEARCH_API_BASE_URL`, `NEXT_PUBLIC_SEARCH_API_KEY`,
   `NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN`, and `NEXT_PUBLIC_BUILD_YEAR`.
3. Keep the workflow `env:` blocks aligned (coordinate with P0-1).

**How to verify.** Run `npm run assert:build-env-contract` with a deliberately
missing var and confirm it fails; with all set, confirm it passes.

---

### P2-4. `home_wizard_choices.json` is manually copied with no sync check

**Status: RESOLVED.** `scripts/codegen/sync-home-wizard-choices.sh` exists
and `deploy-public-www.yml` runs it with `--check` before every staging
build.

**Problem.** `shared/home_wizard/home_wizard_choices.json` is the canonical file
(also a Flutter asset) and is manually copied to
`apps/public_www/src/data/home_wizard_choices.json`. There is no sync script or
CI check (unlike the staging fixture).

**Why it matters.** Editing the canonical file without updating the copy
silently breaks www/Flutter parity.

**Where.**
- Canonical: `shared/home_wizard/home_wizard_choices.json`.
- Copy: `apps/public_www/src/data/home_wizard_choices.json` (imported in
  `apps/public_www/src/lib/home-wizard/choices.ts`).
- Pattern to mirror: `scripts/codegen/sync-activity-search-staging-fixture.sh`.

**Fix steps.**
1. Add a small sync script (copy canonical → `src/data/`) under `scripts/` or an
   npm script in `apps/public_www/package.json`.
2. Add a CI check that fails if the two files differ (e.g. `diff` or a
   `--check` mode), wired into the public-www workflow.

**How to verify.** Edit canonical only; CI/check fails. Run sync; check passes.

---

### P2-5. Missing root-locale redirects for several routes

**Status: RESOLVED.** `inject-static-redirects.mjs` now covers `/`,
`/about/`, `/search/`, `/privacy/`, `/terms/`, and `/activity/` (with a
query-preserving script for `/activity/?id=`).

**Problem.** Only `/` and `/about/` get static root redirects to `/en/...`.
`/search/`, `/privacy/`, `/terms/`, `/activity/` have no non-locale entry.

**Where.** `apps/public_www/scripts/inject-static-redirects.mjs:13-16`.

**Fix steps.** Add redirect entries for the remaining top-level routes to the
default locale; keep query strings intact for `/activity/?id=`.

**How to verify.** Build, then open `out/search/index.html` (etc.) and confirm a
redirect to `/en/search/` is present.

---

### P2-6. Missing `favicon.ico`

**Status: RESOLVED.** `apps/public_www/public/favicon.ico` is a multi-size
ICO of the logo mark (with `public/favicon.svg` as the vector copy) and is
referenced from the root layout metadata.

**Problem.** Root metadata references `/favicon.ico`
(`apps/public_www/src/app/layout.tsx:42-44`) but no `favicon.ico` exists in
`public/` or `src/app/`. The browser request 404s.

**Fix steps.** Add a real `favicon.ico` to `apps/public_www/public/` (or
`src/app/favicon.ico` per Next.js App Router convention), or remove the
`icons` metadata if intentionally unbranded.

**How to verify.** Build; confirm `out/favicon.ico` exists and the request 200s.

---

### P2-7. Accessibility / HTML validity issues

**Status: RESOLVED.** Home and search pages render an `sr-only` `<h1>`; the
activity-detail CTA is a link styled as a button (no nested interactive
elements); the loading state has `aria-live="polite"`.

**Problem & where.**
1. No page `<h1>` on home and search pages (only `<h2>`):
   `apps/public_www/src/components/pages/discovery-home-page.tsx`,
   `search-results-page.tsx`.
2. Nested interactive elements — a `<button>` inside an `<a>` (invalid HTML):
   `apps/public_www/src/components/pages/activity-detail-page.tsx:179-183`.

**Why it matters.** Heading hierarchy affects a11y and SEO; nested interactive
elements are invalid and confuse assistive tech.

**Fix steps.**
1. Add a single visible `<h1>` per page (can be visually-styled but present).
2. Replace `<a><Button/></a>` with either a link styled as a button, or a button
   that navigates — not both nested.

**How to verify.** `npm test`; manual axe/lighthouse a11y pass; visual check.

---

### P2-8. Reads of `NEXT_PUBLIC_*` bypass `site-config.ts`

**Problem.** Several files read `process.env.NEXT_PUBLIC_*` directly instead of
going through `src/lib/site-config.ts`, which `.cursorrules` requires.

**Where.**
- `apps/public_www/src/app/layout.tsx` (GTM/Meta Pixel IDs, allowed hosts).
- `apps/public_www/src/components/shared/analytics-resource-hints.tsx`,
  `google-tag-manager.tsx`, `meta-pixel.tsx`.
- `apps/public_www/src/lib/google-maps/config.ts`.
- `apps/public_www/src/lib/seo.ts:54` (partially justified — keep if it needs a
  test fallback, but document why).

**Fix steps.** Add typed getters in `site-config.ts` and route these reads
through it. Note Next.js requires **static** property access for inlining, so
follow the existing patterns in `site-config.ts` exactly.

**How to verify.** Build + typecheck; confirm analytics/maps still initialize
when their env vars are set.

---

## P3 — Low / nice-to-have

### P3-1. Unused `HomeWizardSection` component and `homeWizard` content

`HomeWizardSection` is registered in the page grid and has copy in
`content/en.json`, but no content page uses `"component": "homeWizard"`. Decide:
wire it into a page, or remove the component, grid registration, and copy.
**Where:** `apps/public_www/src/components/sections/home-wizard/`,
`content/en.json:196-198`.

### P3-2. OpenAPI search spec lacks error responses

`docs/api/search.yaml` documents only `200`; the handler returns `400`/`500`.
Add `400`/`500` response schemas to match the implementation.

### P3-3. Search Lambda response omits some security headers

`backend/src/app/api/search.py:298-316` builds a partial header set, unlike
`json_response()` (`responses.py:60-77`) which adds `X-Frame-Options`,
`Cache-Control`, etc. Align the custom response with `json_response()` headers.

### P3-4. CSP `img-src` is very permissive

`apps/public_www/scripts/inject-csp-meta.mjs` allows `img-src 'self' data:
https:` (any HTTPS origin). If the set of image hosts is known (CDN/API),
tighten to an allow-list.

### P3-5. Logging hygiene

- Migration seed logs unmasked email (`backend/db/migrations/.../seed.py`
  around lines 67/109/125). Use `mask_email()` / `mask_pii()`.
- `passwordless.py:14` uses stdlib `logging.getLogger` instead of `get_logger()`
  — minor consistency fix.

### P3-6. Public exposure of `manager_id`

Public search org responses include `manager_id` (a Cognito sub):
`backend/src/app/api/schemas.py:23`, `search.py` (~line 200). Confirm this is
intentional; if not, drop it from the public schema.

### P3-7. Test coverage gaps

No tests for `search-results-page`, `activity-detail-page`, the live
`search-client` API path, navbar/search panel, footer, or
`fetchActivityListingById`; no Playwright e2e for public_www (admin_web has it).
There is no end-to-end test of `search.lambda_handler` with a mock API Gateway
event. Add targeted unit tests where cheap; consider a minimal e2e later.

### P3-8. Doc drift

`apps/public_www/README.md:35` references `next.config.js`; the actual file is
`next.config.ts`.

### P3-9. Missing shared API client packages

`.cursorrules` and `scripts/codegen/README.md` reference
`packages/api_client_ts` and `packages/api_client_dart`, which do not exist.
admin_web uses `openapi-typescript`; public_www and Flutter hand-write clients
(drift risk). Either build the shared packages or update the docs to reflect
reality and add a CI check that generated admin types are committed.

---

## Suggested execution order

Resolved so far: P0-1, P0-2, P1-2, P1-3 (option 1), P2-1, P2-3, P2-4, P2-5,
P2-6, P2-7. Remaining, in order:

1. **P1-1** (aws_proxy for in-VPC Cognito) — architectural correctness/runtime.
2. **P2-2** (search input validation), **P2-8** (`site-config.ts` env reads).
3. P3 cleanup.

## Notes / things that are actually fine (do not "fix")

- `create_auth_challenge` calling SES in-VPC works — the VPC has an SES
  interface endpoint (`api-stack.ts:204`).
- `images.unoptimized: true` is intentional for `output: 'export'`.
- SQL injection: search uses parameterized SQLAlchemy ORM throughout — safe.
- No `dangerouslySetInnerHTML`, `eval`, `new Function`, `style={...}`, `: any`,
  or `@ts-ignore` were found in `apps/public_www/src` — good.
- All Alembic revision IDs are ≤ 32 chars; no Python file exceeds 500 lines.
