# Lambda Catalog

This document lists the backend Lambda functions, their handlers, and
their primary responsibilities.

## Runtime and packaging

- Runtime: Python 3.12.
- Packaging: deterministic bundling (no bytecode files, repeatable output).
- CDK runs `backend/scripts/run-cdk-app.sh`, which builds the local
  bundle via `backend/scripts/build_lambda_bundle.py` before synth/deploy.
- `build_lambda_bundle.py` caches Python dependencies under
  `backend/.lambda-build/deps-cache/` using a hash of
  `backend/requirements.txt` and runtime settings, so repeat synth runs do
  not reinstall pip packages unless requirements change. Cache pruning keeps
  only the most recent keys (default: 3), configurable with
  `LAMBDA_DEPS_CACHE_RETENTION` or `--cache-retention`.

## API Gateway Lambdas

### Listing events ingest
- Function: ListingEventsIngestFunction
- Handler: backend/lambda/listing_events_ingest/handler.py
- Trigger: API Gateway `POST /v1/listing-events`
- Auth: API key + device attestation authorizer (same as public search)
- Purpose: accept first-party listing funnel events (search, view, CTA,
  lead) from public www. Does not store PII. GA4 remains the board `web`
  tool source.
- DB access: RDS Proxy with IAM auth (`siutindei_admin`), INSERT on
  `listing_events`
- Endpoint contract: [`docs/api/search.yaml`](../api/search.yaml)

### Listing events rollup
- Function: ListingEventsRollupFunction
- Handler: backend/lambda/listing_events_rollup/handler.py
- Trigger: EventBridge cron `15 16 * * ? *` (16:15 UTC / 00:15 HKT)
- Purpose: rebuild yesterday's `listing_events_daily` rows from
  `listing_events` so `v_funnel_daily` has data. `bookings_confirmed`
  stays 0.
- DB access: RDS Proxy with IAM auth (`siutindei_admin`)
- Manual backfill: invoke with `{"day": "YYYY-MM-DD"}`

### Activity search
- Function: SiutindeiSearchFunction
- Handler: backend/lambda/search/handler.py
- Trigger: API Gateway `GET /v1/activities/search` and
  `GET /v1/partner/activities/search`
- Auth: API key + device attestation authorizer (mobile route);
  partner API-key authorizer (partner route, org-scoped keys are
  filtered to their organization)
- Purpose: public activity search with cursor pagination
- DB access: RDS Proxy with IAM auth (`activities_app`). Production always
  queries Aurora (`STAGING_SEARCH_DATA_ENABLED=false` on the Lambda).
- Environment:
  - `STAGING_SEARCH_DATA_ENABLED` (always `false` in deployed stacks)
  - `STAGING_SEARCH_DATA_PATH` (bundled fixture path; unused when disabled)

### Admin API
- Function: SiutindeiAdminFunction
- Handler: backend/lambda/admin/handler.py
- Trigger: API Gateway — handles routes under `/v1/admin/*`,
  `/v1/manager/*`, `/v1/user/*`, and `/v1/partner/*` (CRUD resources)
- Auth: Cognito JWT — admin group for `/v1/admin/*`, admin/manager
  group for `/v1/manager/*`, any authenticated user for `/v1/user/*`;
  partner API keys (`x-partner-key`) for `/v1/partner/*`
- Purpose: admin CRUD (including activity categories and partner API key
  management), manager CRUD (filtered by ownership), partner CRUD
  (scope- and organization-filtered by API key), user self-service
  (tickets), Cognito user management, audit logs, media upload, admin
  import/export, and address autocomplete (Nominatim via the AWS/HTTP
  proxy)
- DB access: RDS Proxy with IAM auth (`siutindei_admin`)
- Memory: 1024 MB (cold start is import-bound; CPU scales with memory)
- X-Ray: active tracing (function segment with init/invocation split)
- Cognito user listing resolves group membership with one
  `list_users_in_group` call per managed group (`ADMIN_GROUP`,
  `MANAGER_GROUP`) instead of one `admin_list_groups_for_user` call per
  user, so the proxy hop count is constant per page
- Environment:
  - `SES_SENDER_EMAIL`
  - `SES_TEMPLATE_REQUEST_DECISION` (optional)
  - `SES_TEMPLATE_SUGGESTION_DECISION` (optional)
  - `SES_TEMPLATE_FEEDBACK_DECISION` (optional)
  - `FEEDBACK_STARS_PER_APPROVAL`
  - `NOMINATIM_USER_AGENT`
  - `NOMINATIM_REFERER`
  - `ADMIN_IMPORT_EXPORT_BUCKET`
- For the full endpoint list, see the OpenAPI spec:
  `docs/api/admin.yaml`

### Health check
- Function: HealthCheckFunction
- Handler: backend/lambda/health/handler.py
- Trigger: API Gateway `GET /health`
- Auth: IAM
- Purpose: service health and configuration checks
- DB access: RDS Proxy with IAM auth (`activities_app`)

## Auth and security Lambdas

### Pre sign-up trigger
- Function: AuthPreSignUpFunction
- Handler: backend/lambda/auth/pre_signup/handler.py
- Trigger: Cognito User Pool PRE_SIGN_UP
- Purpose: validation and pre-sign-up hooks

### Define auth challenge
- Function: AuthDefineChallengeFunction
- Handler: backend/lambda/auth/define_auth_challenge/handler.py
- Trigger: Cognito User Pool DEFINE_AUTH_CHALLENGE
- Purpose: choose the next passwordless challenge step

### Create auth challenge
- Function: AuthCreateChallengeFunction
- Handler: backend/lambda/auth/create_auth_challenge/handler.py
- Trigger: Cognito User Pool CREATE_AUTH_CHALLENGE
- Purpose: generate OTP/magic link and send email

### Verify auth challenge
- Function: AuthVerifyChallengeFunction
- Handler: backend/lambda/auth/verify_auth_challenge/handler.py
- Trigger: Cognito User Pool VERIFY_AUTH_CHALLENGE_RESPONSE
- Purpose: validate passwordless challenge response

### Post authentication
- Function: AuthPostAuthFunction
- Handler: backend/lambda/auth/post_authentication/handler.py
- Trigger: Cognito User Pool POST_AUTHENTICATION
- Purpose: update `custom:last_auth_time` after successful login

### Device attestation authorizer
- Function: DeviceAttestationAuthorizer
- Handler: backend/lambda/authorizers/device_attestation/handler.py
- Trigger: API Gateway request authorizer
- Purpose: verify device attestation JWTs for public search
- VPC: **No** (runs outside VPC to fetch JWKS from Firebase)

### Admin group authorizer
- Function: AdminGroupAuthorizerFunction
- Handler: backend/lambda/authorizers/cognito_group/handler.py
- Trigger: API Gateway request authorizer
- Purpose: verify JWT and check user belongs to the `admin` Cognito group
- VPC: **No** (runs outside VPC to fetch JWKS from Cognito)
- Environment: `ALLOWED_GROUPS=admin`

### Manager group authorizer
- Function: ManagerGroupAuthorizerFunction
- Handler: backend/lambda/authorizers/cognito_group/handler.py
- Trigger: API Gateway request authorizer
- Purpose: verify JWT and check user belongs to `admin` or `manager` group
- VPC: **No** (runs outside VPC to fetch JWKS from Cognito)
- Environment: `ALLOWED_GROUPS=admin,manager`

### User authorizer (any authenticated user)
- Function: UserAuthorizerFunction
- Handler: backend/lambda/authorizers/cognito_user/handler.py
- Trigger: API Gateway request authorizer
- Purpose: verify JWT for any authenticated Cognito user (no group requirement)
- VPC: **No** (runs outside VPC to fetch JWKS from Cognito)

### Partner API-key authorizer
- Function: PartnerApiKeyAuthorizerFunction
- Handler: backend/lambda/authorizers/api_key/handler.py
- Trigger: API Gateway request authorizer for `/v1/partner/*` routes
- Purpose: validate the `x-partner-key` header against SHA-256 hashed
  keys in the `api_keys` table; passes key id, scope (`read`/`crud`),
  and organization scope to handlers via authorizer context. Scope and
  organization enforcement happens in the handlers because the cached
  Allow policy covers all partner routes.
- DB access: RDS Proxy with IAM auth (`siutindei_app`; column-scoped
  UPDATE grant for `last_used_at`)
- VPC: **Yes** (needs database access, no public JWKS)
- Cache: authorizer results cached 5 minutes, bounding how long a
  revoked key keeps working
- Concurrency: no reserved concurrency (account unreserved pool is at
  the AWS minimum of 100; authorizer caching keeps invocations low)

## Deployment and maintenance Lambdas

### Migrations
- Function: SiutindeiMigrationFunction
- Handler: backend/lambda/migrations/handler.py
- Trigger: CloudFormation custom resource during deploy
- Purpose: run Alembic migrations and optional seed SQL
- DB access: direct cluster endpoint with password auth

### Admin bootstrap
- Function: AdminBootstrapFunction
- Handler: backend/lambda/admin_bootstrap/handler.py
- Trigger: CloudFormation custom resource (optional)
- Purpose: create a bootstrap admin user and add to admin group

### API key rotation
- Function: ApiKeyRotationFunction
- Handler: backend/lambda/api_key_rotation/handler.py
- Trigger: EventBridge scheduled rule (every 90 days)
- Purpose: rotate the API Gateway API key to limit exposure from compromise
- VPC: Yes
- Permissions: API Gateway key management, Secrets Manager read/write
- Environment:
  - `API_GATEWAY_REST_API_ID`: REST API ID
  - `API_GATEWAY_USAGE_PLAN_ID`: usage plan ID
  - `API_KEY_SECRET_ARN`: Secrets Manager ARN for key storage
  - `API_KEY_NAME_PREFIX`: prefix for key names
  - `GRACE_PERIOD_HOURS`: hours to keep old key active (default 24)

### Manager request processor
- Function: ManagerRequestProcessor
- Handler: backend/lambda/manager_request_processor/handler.py
- Trigger: SQS queue (subscribed to SNS manager request topic)
- Purpose: process async ticket submissions from the SNS topic. Stores
  the ticket in the `tickets` table (idempotent via `ticket_id`) and
  sends a notification email to support/admin.
- DB access: RDS Proxy with IAM auth (`siutindei_admin`)
- VPC: Yes
- Permissions: SES send email
- Environment:
  - `DATABASE_SECRET_ARN`, `DATABASE_NAME`, `DATABASE_USERNAME`,
    `DATABASE_PROXY_ENDPOINT`, `DATABASE_IAM_AUTH`
  - `SES_SENDER_EMAIL`, `SUPPORT_EMAIL`
  - `SES_TEMPLATE_NEW_ACCESS_REQUEST` (optional)
  - `SES_TEMPLATE_NEW_SUGGESTION` (optional)
  - `SES_TEMPLATE_NEW_FEEDBACK` (optional)

### AWS / HTTP proxy
- Function: AwsApiProxyFunction
- Handler: backend/lambda/aws_proxy/handler.py
- Trigger: Lambda-to-Lambda invocation (from in-VPC Lambdas)
- Purpose: generic proxy for AWS API calls and outbound HTTP requests
  that cannot be made from inside the VPC
- VPC: **No** (runs outside VPC for internet access)
- X-Ray: active tracing (each proxied call is its own trace; callers do not
  propagate the trace header, so hops are correlated by time, not linked)
- Allow-lists:
  - `ALLOWED_ACTIONS`: comma-separated `service:action` pairs for AWS
    API calls (e.g. `cognito-idp:list_users`)
  - `ALLOWED_HTTP_URLS`: comma-separated URL prefixes for outbound HTTP
    requests (e.g. `https://api.example.com/v1/`)
- Security: only invocable by Lambdas granted `lambda:InvokeFunction`;
  IAM role scoped to specific AWS actions; all requests validated
  against the allow-lists before execution
- Why: Cognito disables PrivateLink when ManagedLogin is configured on
  the User Pool, so a VPC endpoint cannot be used.  This proxy provides
  a reusable channel for any service that is unreachable via PrivateLink.
- Client: in-VPC Lambdas import `app.services.aws_proxy.invoke` (for
  AWS calls) or `app.services.aws_proxy.http_invoke` (for HTTP calls)
