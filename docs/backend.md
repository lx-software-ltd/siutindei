# Backend integration

This guide explains how Siu Tin Dei clients connect to the Python Lambda
backend exposed through API Gateway. It focuses on contracts, authentication,
and performance-conscious use of public search—especially for the marketing
site loading **~100 listings** within the
[2 second target](architecture/performance.md).

Low-level AWS inventory: [`architecture/lambdas.md`](architecture/lambdas.md).
Security requirements: [`architecture/security.md`](architecture/security.md).

## API surface

| Audience | OpenAPI spec | Base path examples |
|---|---|---|
| Public search & listing events | [`docs/api/search.yaml`](api/search.yaml) | `/v1/activities/search`, `/v1/listing-events` |
| Admin, manager, user, health | [`docs/api/admin.yaml`](api/admin.yaml) | `/v1/admin/*`, `/v1/manager/*`, `/v1/user/*` |

**Single source of truth** for paths, methods, query parameters, and schemas is
the YAML specs above—do not duplicate endpoint tables in architecture docs.

Generated clients:

| Package | Path | Consumers |
|---|---|---|
| TypeScript | `packages/api_client_ts/` | `apps/admin_web` (`npm run generate:api`) |
| Dart | `packages/api_client_dart/` | `apps/siutindei_app` |

Regenerate after OpenAPI changes via `scripts/codegen/`.

## Runtime layout

```
API Gateway
    → Lambda handlers (backend/lambda/)
        → backend/src/app/ (services, models, repositories)
            → RDS Proxy → Aurora PostgreSQL
```

- **In-VPC Lambdas** must call Cognito and external HTTP through the AWS/HTTP
  proxy (`app.services.aws_proxy`), not direct boto3 Cognito from the VPC.
- **Migrations** run via Alembic (`backend/db/`); application traffic uses IAM
  auth to RDS Proxy with role `activities_app` (read) / `activities_admin`
  (write).

## Authentication patterns

| Client | Mechanism | Headers / tokens |
|---|---|---|
| Public website & mobile search | API key + device attestation | `x-api-key`, `x-device-attestation` |
| Admin web | Cognito JWT (admin group) | `Authorization: Bearer …` |
| Manager routes | Cognito JWT (`admin` or `manager`) | Bearer token |
| User self-service | Any valid Cognito JWT | Bearer token |
| Partner integrations | DB-backed partner keys | `x-partner-key` (see admin OpenAPI) |

Public search attestation is validated against configured JWKS; failures follow
`ATTESTATION_FAIL_CLOSED` in production.

Never commit keys or attestation secrets—inject via CI/GitHub Environments or
local `.env` files ignored by git.

## Public website integration

The static site (`apps/public_www`) does **not** use the generated TS client
for search; it uses a thin `fetch` wrapper in
`apps/public_www/src/lib/activities/search-client.ts` so the bundle stays small
and CSP stays `connect-src 'self'`.

### Build-time environment

Read through `apps/public_www/src/lib/site-config.ts` (static
`process.env.NEXT_PUBLIC_*` access only—dynamic env lookups are empty in the
browser).

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_SITE_ORIGIN` | Canonical site URL (required at build) |
| `NEXT_PUBLIC_SEARCH_API_BASE_URL` | Base URL for `new URL('/v1/activities/search', base)` — **use the website origin in production** to enable CloudFront edge cache |
| `NEXT_PUBLIC_SEARCH_API_KEY` | Public search API key |
| `NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN` | Static attestation token for web |
| `NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED` | `true` → load fixture JSON instead of API (staging only) |
| `NEXT_PUBLIC_STAGING_SEARCH_FIXTURE_URL` | Optional override for fixture path |

CSP `connect-src` is computed at build time in `scripts/inject-csp-meta.mjs`.
Same-origin search avoids adding the API hostname to CSP.

### Search request flow

1. UI builds filters → `filtersToApiParams` in `search-params.ts`.
2. `fetchActivitySearch` sets query params: `age`, `area_id`, `category_id`
   (repeatable), `activity_id`, `cursor`, `limit` (default **50**, max **200**
   per OpenAPI).
3. JSON response: `{ items: [...], next_cursor }` mapped to typed listings.

For **100 listings** in one view, pass `limit: 100` (search results page may
use a higher cap for client-side `q` filtering—prefer tuning filters over
maxing `limit` without need).

### Listing events (funnel telemetry)

Consented `search` / `view_item` / `generate_lead` events POST to
`/v1/listing-events` on the same origin (see [`public-www.md`](architecture/public-www.md)).
Staging fixture mode skips ingest.

### Edge cache interaction

When search goes through the website CloudFront distribution:

- Cache key includes **all query strings**; TTL **300 s**.
- Cache **hits** do not re-run per-request API key checks at origin (public
  catalog semantics). Abuse mitigation is at WAF/edge.

Direct integration tests against `siutindei-api.*` remain valid for mobile and
debugging but bypass website edge cache.

## Admin web integration

`apps/admin_web` uses Cognito hosted UI / PKCE and calls API Gateway with the
user’s access token.

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | API Gateway stage URL (typically ends with `/prod`) |
| `NEXT_PUBLIC_COGNITO_DOMAIN` | Hosted UI domain |
| `NEXT_PUBLIC_COGNITO_CLIENT_ID` | App client ID |
| `NEXT_PUBLIC_COGNITO_USER_POOL_ID` | Pool ID |

Use the generated OpenAPI client for typed admin CRUD. Admin list endpoints are
cursor-paginated—do not assume single large pages for tables.

## Mobile app integration

Flutter uses `packages/api_client_dart` with Amplify/Cognito configuration
passed via `--dart-define`. Public search uses the same `/v1/activities/search`
contract as the website; prefer cursor pagination for long lists.

Staging may use `STAGING_SEARCH_FIXTURE_URL` dart-define (see `AGENTS.md` /
fixture sync scripts).

## Performance guidelines (backend owner)

When supporting the [100-listing / 2 s goal](architecture/performance.md):

1. **Honor `limit`** — avoid N+1 queries per listing row; batch organization,
   location, pricing, and schedule data in the search service layer.
2. **Stable sort for cursors** — pagination orders by schedule timing; broken
   ordering causes duplicate/missing rows under load.
3. **Keep list DTOs lean** — detail pages may fetch `activity_id` with
   `limit=1` and `highPriority` fetch on the client.
4. **Monitor** — search Lambda p99, API 5xx, and Aurora connections
   (`architecture/aws-assets-map.md`).
5. **Do not enable API Gateway stage cache** for cost reasons; website
   CloudFront behavior is the intentional cache layer
   (`architecture/overview.md`).

## Local development

1. PostgreSQL + migrations: see `AGENTS.md` (Cloud / CI) or
   [`architecture/setup.md`](architecture/setup.md).
2. Run backend unit tests:
   `PYTHONPATH=backend/src DATABASE_URL=… python3 -m pytest tests backend -q`
3. Point `NEXT_PUBLIC_SEARCH_API_BASE_URL` at a deployed staging API **or** use
   staging fixture mode for pure frontend work.

## Changing the API

Any new Lambda route requires (owner workflow):

1. Register in API Gateway CDK (`backend/infrastructure/lib/api-stack.ts`).
2. Update the correct OpenAPI file.
3. Update [`architecture/lambdas.md`](architecture/lambdas.md).

Board agents must not modify infrastructure or migrations; file follow-up work
for owners when the brief requires it.

## Related documentation

- [`architecture/performance.md`](architecture/performance.md) — metrics and tuning
- [`docs/frontend.md`](frontend.md) — client-specific optimization
- [`architecture/public-www.md`](architecture/public-www.md) — edge proxy and env
- [`api/search.yaml`](api/search.yaml) — search API reference
