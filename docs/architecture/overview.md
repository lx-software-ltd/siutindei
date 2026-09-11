# Architecture Overview

This document describes the current architecture for the mobile app,
admin console, and backend services.

## High-level diagram

```
Public Website (Next.js static export)        Flutter Mobile / Next.js Admin
        |                                              |
        v                                              v
   CloudFront + S3                              Cognito (Auth)
                                                      |
                                                      v
                                                  API Gateway
                                                      |
                                                      v
                                                Lambda (Python)
                                                      |
                                                      v
                                                  RDS Proxy
                                                      |
                                                      v
                                          Aurora PostgreSQL (Serverless v2)
```

## Components

### Mobile app (Flutter)
- Users browse activities and filter by age, district, price, time/day,
  and language.
- Uses generated Dart API client from OpenAPI specs.
- Device attestation uses Firebase App Check (Play Integrity / App Attest).

### Admin console (Next.js App Router)
- Admin users manage organizations, activities, schedules, and pricing.
- Hosted on Amplify Hosting (release jobs triggered in CI).

### Public website (Next.js static export)
- Marketing/landing site for Siu Tin Dei (`apps/public_www`).
- Deployed as a static export to S3 and served via CloudFront with
  WAF, HSTS, CSP, and the standard security headers.
- Two parallel CloudFront distributions (production + staging) live in the
  same `lxsoftware-siutindei-public-www` CloudFormation stack, with the
  staging distribution noindexed via `X-Robots-Tag` and a deny-all
  `robots.txt` synced by the deploy script.
- Releases are deployed to staging on push-to-main, then promoted to
  production via `workflow_dispatch` (`Promote Public Website Release`).
  Promotion can be a fresh production-built static export *or* an
  S3-only artifact copy from `releases/<id>/` on the staging bucket.
- See [`docs/architecture/public-www.md`](public-www.md) for the design.

### Backend
- API Gateway exposes REST endpoints for public search, admin CRUD,
  manager CRUD, and user self-service operations.
- For the full list of API routes, request/response schemas, and
  authentication requirements, see the OpenAPI specs:
  - [`docs/api/search.yaml`](../api/search.yaml) — public activity search
  - [`docs/api/admin.yaml`](../api/admin.yaml) — admin, manager, user, and health endpoints
- Lambda functions in `backend/lambda/` call into shared code in
  `backend/src/app`.
- See [`docs/architecture/lambdas.md`](lambdas.md) for a full function inventory.
- A generic AWS/HTTP proxy Lambda (`AwsApiProxyFunction`) runs outside
  the VPC and provides a channel for in-VPC Lambdas to call services
  that are unreachable via PrivateLink (e.g. Cognito with ManagedLogin).
  Requests are gated by allow-lists (`ALLOWED_ACTIONS` for AWS API
  calls, `ALLOWED_HTTP_URLS` for outbound HTTP).  See
  `backend/src/app/services/aws_proxy.py`.
- Asynchronous messaging (SNS + SQS) is used for manager access requests
  and organization suggestions. See [`docs/architecture/aws-messaging.md`](aws-messaging.md).
- SQLAlchemy models map to Aurora PostgreSQL.
- Alembic manages schema migrations, executed via a custom resource Lambda
  during deploy.
- Cognito User Pool secures admin/manager routes; any-user routes require
  only a valid JWT. Passwordless email challenges and federated sign-in
  (Google, Apple) are supported.
- API keys are rotated automatically every 90 days via a scheduled Lambda.

## Data model

Key entities:
- `organizations` (with manager assignment)
- `locations` (district used for filtering)
- `activities`
- `activity_locations`
- `activity_pricing` (per-class, per-month, per-sessions)
- `activity_schedule` (weekly only; languages per schedule)
- `activity_schedule_entries` (per-day timeslots for schedules)
- `organization_access_requests` (manager access workflow)
- `organization_suggestions` (user-submitted place suggestions)
- `audit_log` (automatic change tracking via triggers)

All times are stored in UTC.
See [`docs/architecture/database-schema.md`](database-schema.md) for full table details.

## Database and migrations

- Aurora PostgreSQL Serverless v2.
- RDS Proxy with IAM auth for Lambda connections.
- CDK-managed clusters enable the RDS HTTP Data API for the
  lx-software Executive Board stack (`rds-data`). Product Lambdas
  still use RDS Proxy.
- Public www posts consented listing events to `POST /v1/listing-events`;
  a nightly job fills `listing_events_daily` for `v_funnel_daily`.
  GA4 stays the board `web` tool; Aurora is first-party counts only.
- Alembic migrations live under `backend/db/`.
- Seed data stored in `backend/db/seed/seed_data.sql`.
- Migrations run via a custom resource Lambda using password auth.
- Application traffic uses IAM auth via the proxy and the `activities_app` role.
- Deployments reuse existing DB clusters, proxies, and VPCs when detected.

## CI/CD

- GitHub Actions with OIDC for AWS access.
- Deploy workflows for mobile, admin, backend, iOS.
- Board engineering runner: `board-agent.yml` (Cursor CLI on
  `staging`), `board-merge-staging.yml` (policy squash), and
  `board-promote.yml` (opens `staging → main` for the owner). See
  [`executive-board-autonomy-siutindei-appendix-a.md`](executive-board-autonomy-siutindei-appendix-a.md).
- CDK bootstrap workflow for initial environment setup.
- Lockfile checks for Flutter, Node, and iOS.
- Amplify promotion workflow with gating (staging -> main).
- Dependabot enabled for automated dependency updates (see below).
- Infrastructure tests validate CDK templates for new and imported
  database resources.

## Dependency Management

Dependabot is configured (`.github/dependabot.yml`) to automatically create
pull requests for dependency updates:

| Ecosystem | Directory | Scope |
|-----------|-----------|-------|
| GitHub Actions | `/` | CI workflow action versions |
| npm | `/backend/infrastructure` | CDK and TypeScript dependencies |
| npm | `/apps/public_www` | Public marketing site |
| npm | `/apps/admin_web` | Admin console |
| pip | `/backend` | Python Lambda dependencies |
| pub | `/apps/siutindei_app` | Flutter/Dart dependencies |

**Configuration:**
- Weekly updates (Mondays) to reduce PR noise.
- Related dependencies grouped into single PRs (AWS, Firebase, database, etc.).
- Major version updates ignored (require manual review).
- PRs labeled by ecosystem for easy filtering.

## Security

- No long-lived AWS credentials in GitHub.
- IAM auth for RDS Proxy, TLS enforced on DB connections.
- Secrets stored in GitHub Secrets or AWS Secrets Manager.
- Public activity search requires an API key plus device attestation (JWKS-validated).
- Admin routes require membership in the Cognito `admin` group.
- Manager routes require `admin` or `manager` group membership.
- User routes require any valid Cognito JWT (no group requirement).
- API keys are rotated every 90 days via a scheduled Lambda.
- Optional CDK parameters can bootstrap an initial admin user.
- Passwordless email sign-in uses Cognito custom auth triggers.
- Hosted UI enables Google and Apple IdPs via OAuth.
- Database audit logging tracks all data changes (see [`audit-logging.md`](audit-logging.md)).
- See [`docs/architecture/security.md`](security.md) for full security guidelines.

## Observability

- CloudWatch logs for all Lambda functions (KMS encrypted, 90-day retention).
- X-Ray tracing enabled for API Gateway, with active tracing on the admin
  and AWS-proxy Lambdas.
- Operational alarms (API Gateway 5XX and volume-gated p99 latency,
  search/admin Lambda errors, throttles, and per-function p99 duration,
  Aurora ACU utilization and connection count, manager request DLQ) publish
  to the KMS-encrypted `ops-alerts` SNS topic, with an
  optional email subscription via the `OpsAlertsEmail` parameter. See
  [`aws-assets-map.md`](aws-assets-map.md) for the alarm inventory.
- Structured JSON logging with request ID correlation.

## Caching

- Public search responses are cached at the CloudFront edge (5-minute TTL) via
  the public-website distribution's `/v1/activities/search` behavior. The API
  Gateway stage cache cluster is intentionally disabled (Checkov CKV_AWS_120 is
  suppressed via `skip-check` in `.checkov.yaml`); see
  [`decisions.md`](decisions.md) for the cost rationale.
- Cache keys include all search query parameters.
- Client-side caching with stale-while-revalidate in Flutter (planned).
- See [`docs/architecture/cloudflare-optimization.md`](cloudflare-optimization.md) for edge caching strategy.
