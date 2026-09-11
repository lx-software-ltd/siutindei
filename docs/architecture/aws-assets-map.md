# AWS Assets Map - Backend Deploy

This document maps all AWS resources created by the `backend-deploy` workflow (`.github/workflows/deploy-backend.yml`).

**Stack Name:** `lxsoftware-siutindei`  
**CDK App:** `backend/infrastructure/bin/app.ts`  
**Stack Definition:** `backend/infrastructure/lib/api-stack.ts`

> Sister stacks created from the same CDK app:
>
> - `lxsoftware-siutindei-admin-web` — admin console CloudFront/S3
>   (`backend/infrastructure/lib/admin-web-stack.ts`).
> - `lxsoftware-siutindei-public-www` — public website CloudFront/S3, both
>   production and staging environments
>   (`backend/infrastructure/lib/public-www-stack.ts`). See
>   [`public-www.md`](public-www.md) for the full asset list.
> - `lxsoftware-siutindei-waf` — WAFv2 WebACL in `us-east-1` reused by both
>   admin-web and public-www CloudFront distributions
>   (`backend/infrastructure/lib/waf-stack.ts`).

---

## CDK Bootstrap Stack (CDKToolkit)

Created once per account/region when `cdk bootstrap` runs. Not part of the main stack but required for deployment.

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| S3 Bucket | `StagingBucket` | `cdk-*-assets-{account}-{region}` | Stores CDK assets (Lambda bundles, etc.) |
| ECR Repository | `StagingRepository` | `cdk-*-container-assets-{account}-{region}` | For container-based assets (unused in this stack) |
| KMS Key | `StagingKey` | Auto-generated | Encrypts assets in S3/ECR |
| IAM Role | `DeployActionRole` | Auto-generated | Role for CDK deployments |
| IAM Role | `FilePublishingRole` | Auto-generated | Role for publishing to S3 |
| IAM Role | `ImagePublishingRole` | Auto-generated | Role for publishing to ECR |
| IAM Role | `LookupRole` | Auto-generated | Role for cross-account lookups |
| SSM Parameter | `/cdk-bootstrap/{qualifier}/version` | `/cdk-bootstrap/*/version` | Tracks bootstrap version |

---

## Application S3 Buckets

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| S3 Bucket | `OrganizationImagesBucket` | `lxsoftware-siutindei-org-media-{account}-{region}` | Public bucket for organization images |
| S3 Bucket | `OrganizationImagesLogBucket` | `lxsoftware-siutindei-org-media-logs-{account}-{region}` | Access logs for org media bucket |
| S3 Bucket | `AdminImportExportBucket` | `lxsoftware-siutindei-org-imprt-{account}-{region}` | Admin import/export JSON storage |
| S3 Bucket | `AdminImportExportLogBucket` | `lxsoftware-siutindei-org-imprt-logs-{account}-{region}` | Access logs for admin import/export bucket |

---

## Network Infrastructure

### VPC and Subnets

**Created only if `EXISTING_VPC_ID` is not provided.**

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| VPC | `SiutindeiVpc` | `lxsoftware-siutindei-vpc` | 2 AZs, no NAT Gateway |
| Internet Gateway | `SiutindeiVpcIGW*` | Auto-generated | Attached to VPC |
| Public Subnet | `SiutindeiVpcPublicSubnet*` | Auto-generated | 2 subnets (1 per AZ) |
| Private Subnet | `SiutindeiVpcPrivateSubnet*` | Auto-generated | 2 isolated subnets (1 per AZ) |
| Route Table | `SiutindeiVpcPublicSubnet*RouteTable*` | Auto-generated | Public route table |
| Route Table | `SiutindeiVpcPrivateSubnet*RouteTable*` | Auto-generated | Private route table |
| Route | `SiutindeiVpcPublicSubnet*DefaultRoute*` | Auto-generated | 0.0.0.0/0 → IGW |
| VPC Gateway Attachment | `SiutindeiVpcVPCGW*` | Auto-generated | IGW attachment |

---

## Security Groups

**Created only if corresponding `EXISTING_*_SECURITY_GROUP_ID` is not provided.**

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| Security Group | `LambdaSecurityGroup` | `lxsoftware-siutindei-lambda-sg` | For Lambda functions (RETAIN policy) |
| Security Group | `MigrationSecurityGroup` | `lxsoftware-siutindei-migration-sg` | For migration Lambda (RETAIN policy) |
| Security Group | `DatabaseSecurityGroup` | `lxsoftware-siutindei-db-sg` | For Aurora cluster |
| Security Group | `ProxySecurityGroup` | `lxsoftware-siutindei-proxy-sg` | For RDS Proxy |

**Security Group Rules (managed automatically unless existing SGs are used):**

| Source SG | Target SG | Port | Description |
|-----------|-----------|------|-------------|
| `ProxySecurityGroup` | `DatabaseSecurityGroup` | 5432 | RDS Proxy → Aurora |
| `LambdaSecurityGroup` | `ProxySecurityGroup` | 5432 | Lambda → RDS Proxy |
| `MigrationSecurityGroup` | `DatabaseSecurityGroup` | 5432 | Migration Lambda → Aurora (direct) |

---

## VPC Endpoints

**Created only when a new VPC is created (not when `EXISTING_VPC_ID` is used).**

| Resource Type | Logical ID | Service | Notes |
|--------------|------------|---------|-------|
| Gateway Endpoint | `S3Endpoint` | S3 | Gateway endpoint (no cost) |
| Interface Endpoint | `SecretsManagerEndpoint` | Secrets Manager | For DB secret access |
| Interface Endpoint | `StsEndpoint` | STS | For IAM auth token generation |
| Interface Endpoint | `CloudWatchLogsEndpoint` | CloudWatch Logs | For Lambda logging |
| Interface Endpoint | `SesEndpoint` | SES | For email sending |
| Interface Endpoint | `SnsEndpoint` | SNS | For notifications |
| Interface Endpoint | `RdsEndpoint` | RDS | For IAM authentication tokens |
| Interface Endpoint | `ApiGatewayEndpoint` | API Gateway | For API key rotation |
| Interface Endpoint | `SqsEndpoint` | SQS | For manager request queue |
| Interface Endpoint | `LambdaEndpoint` | Lambda | For invoking the AWS API proxy from in-VPC Lambdas |

**Note:** Cognito IDP VPC endpoint is **not** included because Cognito
disables PrivateLink when ManagedLogin is configured on the User Pool.
Cognito operations are proxied through `AwsApiProxyFunction` instead.

---

## Database Infrastructure

### Secrets Manager

**Created only if `EXISTING_DB_CREDENTIALS_SECRET_NAME` and `EXISTING_DB_CREDENTIALS_SECRET_ARN` are not provided.**

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| Secret | `DBCredentialsSecret` | `lxsoftware-siutindei-database-credentials` | Auto-generates password for `postgres` user |

### KMS

**Created only if a new secret is created (not using existing).**

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| KMS Key | `DatabaseSecretKey` | Auto-generated | Encrypts database secret (rotation enabled) |
| KMS Alias | `DatabaseSecretKeyAlias*` | Auto-generated | Alias for the key |

### RDS Aurora PostgreSQL Serverless v2

**Created only if `EXISTING_DB_CLUSTER_IDENTIFIER` is not provided.**

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| DB Subnet Group | `ClusterSubnets*` | Auto-generated | Private subnets for DB |
| DB Cluster | `Cluster*` | `lxsoftware-siutindei-db-cluster` | Aurora Serverless v2, PostgreSQL 16.4 |
| DB Instance | `Cluster*Instance*` | `lxsoftware-siutindei-db-writer` | Writer instance (serverless v2) |
| IAM Role | `DatabaseMonitoringRole` | Auto-generated | Enhanced monitoring role |
| DB Parameter Group | `ClusterParameterGroup*` | Auto-generated | PostgreSQL parameters |
| DB Cluster Parameter Group | `ClusterParameterGroup*` | Auto-generated | Cluster-level parameters |

**Cluster Configuration:**
- Engine: Aurora PostgreSQL 16.4
- Min Capacity: 0.5 ACU
- Max Capacity: 2 ACU
- Database Name: `siutindei`
- IAM Authentication: Enabled (if `applyImmutableSettings=true`)
- Storage Encryption: Enabled (if `applyImmutableSettings=true`)
- CloudWatch Logs: `postgresql` export enabled
- Monitoring: Enhanced monitoring (60s interval)
- Backups: 14-day automated backup retention, copy tags to snapshots
- Deletion Protection: Enabled
- HTTP Data API: Enabled (`enableDataApi: true` on the CDK-managed
  cluster) so the lx-software Executive Board stack can run
  `rds-data` against `v_catalog_health`, `v_funnel_daily`, and
  `v_provider_pipeline`. Product Lambdas still connect through RDS
  Proxy. This property is not applied to clusters imported via
  `EXISTING_DB_*`.
- Note: for clusters imported via `EXISTING_DB_*`, backup retention,
  deletion protection, and the HTTP Data API must be applied
  out-of-band (see `docs/deployment/launch-checklist.md`)

### RDS Proxy

**Created only if `EXISTING_DB_PROXY_NAME` is not provided.**

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| DB Proxy | `Proxy*` | `lxsoftware-siutindei-db-proxy` | IAM auth enabled, TLS required |
| DB Proxy Target Group | `ProxyTargetGroup*` | Auto-generated | Targets Aurora cluster |
| DB Proxy Target | `ProxyTarget*` | Auto-generated | Links proxy to cluster |

---

## Cognito Authentication

### User Pool

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| User Pool | `SiutindeiUserPool` | `lxsoftware-siutindei-user-pool` | Email sign-in, auto-verify enabled |
| User Pool Domain | `SiutindeiUserPoolDomain` | `{CognitoDomainPrefix}.auth.{region}.amazoncognito.com` | Domain prefix from parameter |
| User Pool Client | `SiutindeiUserPoolClient` | Auto-generated | OAuth client (no secret) |
| User Pool Group | `AdminGroup` | `admin` | Admin group |
| User Pool Group | `ManagerGroup` | `manager` | Manager group |

### Identity Providers

| Resource Type | Logical ID | Provider Name | Notes |
|--------------|------------|---------------|-------|
| User Pool Identity Provider | `GoogleIdentityProvider` | `Google` | Google OAuth |
| User Pool Identity Provider | `AppleIdentityProvider` | `SignInWithApple` | Apple Sign In |

**User Pool Client Configuration:**
- OAuth Flows: `code`
- OAuth Scopes: `openid`, `email`, `profile`
- Supported Providers: `Google`, `SignInWithApple`
- Explicit Auth Flows: `ALLOW_CUSTOM_AUTH`, `ALLOW_REFRESH_TOKEN_AUTH`

---

## Lambda Functions

Each Lambda function created by `PythonLambda` construct includes:
- Lambda function
- IAM execution role
- KMS key for environment variable encryption
- SQS dead-letter queue

### Application Functions

| Function Logical ID | Handler | Memory | Timeout | VPC | Extra Paths |
|---------------------|---------|--------|---------|-----|-------------|
| `SiutindeiSearchFunction` | `lambda/search/handler.lambda_handler` | 512 MB | 30s | Yes | - |
| `SiutindeiAdminFunction` | `lambda/admin/handler.lambda_handler` | 1024 MB | 30s | Yes | - |
| `SiutindeiMigrationFunction` | `lambda/migrations/handler.lambda_handler` | 512 MB | 5 min | Yes | `db` |
| `HealthCheckFunction` | `lambda/health/handler.lambda_handler` | 256 MB | 10s | Yes | - |

### Auth Functions

| Function Logical ID | Handler | Memory | Timeout | VPC | Notes |
|---------------------|---------|--------|---------|-----|-------|
| `AuthPreSignUpFunction` | `lambda/auth/pre_signup/handler.lambda_handler` | 256 MB | 10s | No | Cognito trigger |
| `AuthDefineChallengeFunction` | `lambda/auth/define_auth_challenge/handler.lambda_handler` | 256 MB | 10s | No | Cognito trigger |
| `AuthCreateChallengeFunction` | `lambda/auth/create_auth_challenge/handler.lambda_handler` | 256 MB | 10s | No | Cognito trigger, SES permissions |
| `AuthVerifyChallengeFunction` | `lambda/auth/verify_auth_challenge/handler.lambda_handler` | 256 MB | 10s | No | Cognito trigger |

### Authorizer Functions

| Function Logical ID | Handler | Memory | Timeout | VPC | Notes |
|---------------------|---------|--------|---------|-----|-------|
| `DeviceAttestationAuthorizer` | `lambda/authorizers/device_attestation/handler.lambda_handler` | 256 MB | 5s | No | Device attestation authorizer |
| `AdminGroupAuthorizerFunction` | `lambda/authorizers/cognito_group/handler.lambda_handler` | 256 MB | 5s | No | Admin group authorizer |
| `ManagerGroupAuthorizerFunction` | `lambda/authorizers/cognito_group/handler.lambda_handler` | 256 MB | 5s | No | Manager group authorizer |
| `UserAuthorizerFunction` | `lambda/authorizers/cognito_user/handler.lambda_handler` | 256 MB | 5s | No | Any-user authorizer |
| `PartnerApiKeyAuthorizerFunction` | `lambda/authorizers/api_key/handler.lambda_handler` | 256 MB | 10s | Yes | Partner API-key authorizer (DB lookup via RDS Proxy) |

### Other Functions

| Function Logical ID | Handler | Memory | Timeout | VPC | Notes |
|---------------------|---------|--------|---------|-----|-------|
| `AdminBootstrapFunction` | `lambda/admin_bootstrap/handler.lambda_handler` | 256 MB | 30s | Yes | Custom resource handler |
| `AwsApiProxyFunction` | `lambda/aws_proxy/handler.lambda_handler` | 256 MB | 15s | No | AWS/HTTP proxy for in-VPC Lambdas |
| `ApiKeyRotationFunction` | `lambda/api_key_rotation/handler.lambda_handler` | 256 MB | 60s | Yes | Scheduled API key rotation |
| `ListingEventsIngestFunction` | `lambda/listing_events_ingest/handler.lambda_handler` | 256 MB | 10s | Yes | Public listing-event ingest |
| `ListingEventsRollupFunction` | `lambda/listing_events_rollup/handler.lambda_handler` | 256 MB | 60s | Yes | Nightly listing_events_daily rollup |
| `ManagerRequestProcessor` | `lambda/manager_request_processor/handler.lambda_handler` | 512 MB | 10s | Yes | SQS-triggered request processor |

### Lambda Resources Per Function

For each function above, the following resources are created:

| Resource Type | Logical ID Pattern | Notes |
|--------------|-------------------|-------|
| Lambda Function | `{FunctionLogicalID}Function*` | Python 3.12 runtime |
| IAM Role | `{FunctionLogicalID}FunctionServiceRole*` | Execution role |
| IAM Policy | `{FunctionLogicalID}FunctionServiceRoleDefaultPolicy*` | Basic Lambda permissions |
| KMS Key | `{FunctionLogicalID}EnvironmentEncryptionKey*` | Encrypts environment variables (rotation enabled) |
| KMS Alias | `{FunctionLogicalID}EnvironmentEncryptionKeyAlias*` | Alias for the key |
| SQS Queue | `{FunctionLogicalID}DeadLetterQueue*` | DLQ for failed invocations (14-day retention) |
| SQS Queue Policy | `{FunctionLogicalID}DeadLetterQueuePolicy*` | Allows Lambda to send to DLQ |

**Lambda Configuration:**
- Runtime: Python 3.12
- Reserved Concurrency: 25 (default). Functions can opt out by passing
  `reservedConcurrentExecutions: null`; `PartnerApiKeyAuthorizerFunction`
  opts out because the account-wide unreserved pool sits at the AWS
  minimum of 100 (adding another 25-slot reservation fails deployment)
- Environment: `PYTHONPATH=/var/task/src`, `LOG_LEVEL=INFO`
- VPC Subnets: Private with egress (if VPC enabled)
- Dead Letter Queue: Enabled

**Additional IAM Permissions:**

| Function | Additional Permissions |
|----------|------------------------|
| `SiutindeiSearchFunction` | Read DB secret, connect to RDS Proxy as `siutindei_app` |
| `PartnerApiKeyAuthorizerFunction` | Read app DB secret, connect to RDS Proxy as `siutindei_app` |
| `SiutindeiAdminFunction` | Read DB secret, connect to RDS Proxy as `siutindei_admin`, invoke `AwsApiProxyFunction`, SNS publish to manager request topic, SES send email, S3 read/write for org media and admin import/export |
| `AwsApiProxyFunction` | Cognito admin operations (`ListUsers`, `AdminGetUser`, `AdminDeleteUser`, `AdminAddUserToGroup`, `AdminRemoveUserFromGroup`, `AdminListGroupsForUser`, `AdminUserGlobalSignOut`) |
| `SiutindeiMigrationFunction` | Read DB secret, direct connect to Aurora as `postgres`, Cognito user management, CloudFormation invoke permission |
| `HealthCheckFunction` | Read DB secret, connect to RDS Proxy as `siutindei_app` |
| `AuthCreateChallengeFunction` | SES `SendEmail`, `SendRawEmail` for the configured email address |
| `AdminBootstrapFunction` | Cognito `AdminCreateUser`, `AdminUpdateUserAttributes`, `AdminSetUserPassword`, `AdminAddUserToGroup`, CloudFormation invoke permission |
| `ApiKeyRotationFunction` | API Gateway key management, Secrets Manager read/write |
| `ManagerRequestProcessor` | Read DB secret, connect to RDS Proxy as `siutindei_admin`, SES send email |

**Lambda Log Groups:**
- Explicitly created by CDK with KMS encryption
- Naming: `/aws/lambda/{function-name}` (e.g., `/aws/lambda/lxsoftware-siutindei-SiutindeiSearchFunction`)
- 90-day retention policy

---

## API Gateway

### REST API

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| REST API | `SiutindeiApi` | `lxsoftware-siutindei-api` | Regional REST API |
| Deployment | `SiutindeiApiDeployment*` | Auto-generated | Deployment for `prod` stage |
| Stage | `SiutindeiApiDeploymentStageprod*` | `prod` | Production stage |

**Stage Configuration:**
- Access Logging: Enabled (to `lxsoftware-siutindei-api-access-logs` - must exist)
- Access Log Format: JSON with standard fields
- Logging Level: INFO
- Data Trace: Disabled
- X-Ray Tracing: Enabled
- Caching: Disabled (no stage cache cluster). Public search responses are
  cached at the CloudFront edge instead — see the public-website distribution
  `/v1/activities/search` behavior in
  [`public-www.md`](./public-www.md#search-api-edge-caching).

**CORS Configuration:**
- Allowed Origins: From `CORS_ALLOWED_ORIGINS` env var or context, defaults to `capacitor://localhost`, `ionic://localhost`, `http://localhost`
- Allowed Methods: `GET`, `OPTIONS`

### API Gateway Resources and Methods

For the complete list of endpoints with request/response schemas, see
the OpenAPI specs: [`docs/api/search.yaml`](../api/search.yaml)
and [`docs/api/admin.yaml`](../api/admin.yaml).

| Resource Path | Method | Authorization | Integration | Notes |
|--------------|--------|---------------|-------------|-------|
| `/health` | GET | IAM | `HealthCheckFunction` | Health check |
| `/v1/activities/search` | GET | Device Attestation + API Key | `SiutindeiSearchFunction` | Cached at CloudFront edge (5-min TTL) |
| `/v1/listing-events` | POST | Device Attestation + API Key | `ListingEventsIngestFunction` | First-party funnel ingest; never cached |
| `/v1/admin/{resource}` | GET, POST | Admin Group | `SiutindeiAdminFunction` | CRUD (orgs, locations, activities, pricing, schedules) |
| `/v1/admin/{resource}/{id}` | GET, PUT, DELETE | Admin Group | `SiutindeiAdminFunction` | CRUD by ID |
| `/v1/admin/organizations/{id}/media` | POST, DELETE | Admin Group | `SiutindeiAdminFunction` | Media upload/delete |
| `/v1/admin/users/{username}/groups` | POST, DELETE | Admin Group | `SiutindeiAdminFunction` | Group management |
| `/v1/admin/cognito-users` | GET | Admin Group | `SiutindeiAdminFunction` | List Cognito users |
| `/v1/admin/cognito-users/{username}` | DELETE | Admin Group | `SiutindeiAdminFunction` | Delete Cognito user |
| `/v1/admin/access-requests` | GET | Admin Group | `SiutindeiAdminFunction` | List access requests |
| `/v1/admin/access-requests/{id}` | PUT | Admin Group | `SiutindeiAdminFunction` | Review access request |
| `/v1/admin/audit-logs` | GET | Admin Group | `SiutindeiAdminFunction` | List audit logs |
| `/v1/admin/audit-logs/{id}` | GET | Admin Group | `SiutindeiAdminFunction` | Get audit log entry |
| `/v1/admin/organization-suggestions` | GET | Admin Group | `SiutindeiAdminFunction` | List suggestions |
| `/v1/admin/organization-suggestions/{id}` | PUT | Admin Group | `SiutindeiAdminFunction` | Review suggestion |
| `/v1/admin/api-keys` | GET, POST | Admin Group | `SiutindeiAdminFunction` | Partner API key management |
| `/v1/admin/api-keys/{id}` | GET, DELETE | Admin Group | `SiutindeiAdminFunction` | Get / revoke partner API key |
| `/v1/manager/{resource}` | GET, POST | Manager Group | `SiutindeiAdminFunction` | Filtered CRUD |
| `/v1/manager/{resource}/{id}` | GET, PUT, DELETE | Manager Group | `SiutindeiAdminFunction` | Filtered CRUD by ID |
| `/v1/partner/activities/search` | GET | Partner API Key | `SiutindeiSearchFunction` | Partner search (org-filtered) |
| `/v1/partner/activities` | GET, POST | Partner API Key | `SiutindeiAdminFunction` | Partner activities CRUD (explicit; literal resource shadows the proxy) |
| `/v1/partner/{proxy+}` | ANY | Partner API Key | `SiutindeiAdminFunction` | Greedy proxy for remaining partner CRUD (orgs, locations, activities/{id}, pricing, schedules); scope/org enforced in Lambda |
| `/v1/user/access-request` | GET, POST | User Auth | `SiutindeiAdminFunction` | Access request |
| `/v1/user/organization-suggestion` | GET, POST | User Auth | `SiutindeiAdminFunction` | Org suggestion |

### API Gateway Gateway Responses

CORS headers are added to API Gateway error responses so the browser can
read error status codes instead of silently blocking them.

| Response Type | Headers Added |
|--------------|---------------|
| `DEFAULT_4XX` | `Access-Control-Allow-Origin`, `Access-Control-Allow-Headers`, `Access-Control-Allow-Methods` |
| `DEFAULT_5XX` | `Access-Control-Allow-Origin`, `Access-Control-Allow-Headers`, `Access-Control-Allow-Methods` |

### API Gateway Authorizers

| Resource Type | Logical ID | Type | Handler | Notes |
|--------------|------------|------|---------|-------|
| Request Authorizer | `DeviceAttestationRequestAuthorizer` | Lambda | `DeviceAttestationAuthorizer` | Validates `x-device-attestation` header, no caching |
| Request Authorizer | `AdminGroupAuthorizer` | Lambda | `AdminGroupAuthorizerFunction` | JWT + admin group check, 5-min cache |
| Request Authorizer | `ManagerGroupAuthorizer` | Lambda | `ManagerGroupAuthorizerFunction` | JWT + admin/manager group check, 5-min cache |
| Request Authorizer | `UserAuthorizer` | Lambda | `UserAuthorizerFunction` | JWT validation (any user), 5-min cache |
| Request Authorizer | `PartnerApiKeyAuthorizer` | Lambda | `PartnerApiKeyAuthorizerFunction` | Validates `x-partner-key` against hashed DB keys, 5-min cache |

### API Gateway API Key and Usage Plan

| Resource Type | Logical ID | Physical Name/ID | Notes |
|--------------|------------|------------------|-------|
| API Key | `MobileSearchApiKey` | `lxsoftware-siutindei-mobile-search-key` | Value from `PublicApiKeyValue` parameter |
| Usage Plan | `MobileSearchUsagePlan` | `lxsoftware-siutindei-mobile-search-plan` | Linked to API key and `prod` stage |

### API Gateway IAM Roles

| Resource Type | Logical ID | Purpose | Notes |
|--------------|------------|---------|-------|
| IAM Role | `ApiGatewayLogRole` | CloudWatch Logs | Allows API Gateway to write access logs |

### API Gateway Account Settings

| Resource Type | Logical ID | Notes |
|--------------|------------|-------|
| Account | `ApiGatewayAccount` | Configures CloudWatch role for API Gateway |

**Note:** The access log group `lxsoftware-siutindei-api-access-logs` is **imported** (not created by CDK). It must exist before deployment.

---

## Operational Alarms (OpsAlarms construct)

Created by `OpsAlarmsConstruct` (`lib/constructs/ops-alarms.ts`).

| Resource Type | Physical Name | Notes |
|--------------|---------------|-------|
| SNS Topic | `lxsoftware-siutindei-ops-alerts` | KMS-encrypted; receives all operational alarms |
| KMS Key + Alias | `lxsoftware-siutindei-kms-ops-alerts` | Topic encryption key (rotation enabled; CloudWatch service principal granted) |
| SNS Subscription | — | Email subscription to `OpsAlertsEmail` (conditional: only when the parameter is non-empty) |
| CloudWatch Alarm | `lxsoftware-siutindei-api-5xx-alarm` | API Gateway 5XX ≥ 5 in 5 min |
| CloudWatch Alarm | `lxsoftware-siutindei-api-latency-p99-alarm` | API Gateway p99 latency ≥ 3 s for 15 min, evaluated only in 5-min periods with ≥ 50 requests (metric math `IF(samples >= 50, p99)`; sparser periods are treated as missing) |
| CloudWatch Alarm | `lxsoftware-siutindei-search-lambda-duration-p99-alarm` | Search Lambda p99 `Duration` ≥ 3 s for 15 min |
| CloudWatch Alarm | `lxsoftware-siutindei-search-lambda-errors-alarm` | Search Lambda errors ≥ 3 in 5 min |
| CloudWatch Alarm | `lxsoftware-siutindei-search-lambda-throttles-alarm` | Search Lambda throttles ≥ 1 |
| CloudWatch Alarm | `lxsoftware-siutindei-admin-lambda-duration-p99-alarm` | Admin Lambda p99 `Duration` ≥ 10 s for 15 min |
| CloudWatch Alarm | `lxsoftware-siutindei-admin-lambda-errors-alarm` | Admin Lambda errors ≥ 3 in 5 min |
| CloudWatch Alarm | `lxsoftware-siutindei-admin-lambda-throttles-alarm` | Admin Lambda throttles ≥ 1 |
| CloudWatch Alarm | `lxsoftware-siutindei-aurora-acu-utilization-alarm` | Aurora ACU utilization ≥ 90% for 15 min |
| CloudWatch Alarm | `lxsoftware-siutindei-aurora-connections-alarm` | Aurora connections ≥ 300 for 15 min |

The pre-existing manager-request DLQ alarm (`lxsoftware-siutindei-manager-request-dlq-alarm`) is also routed to the ops-alerts topic. Thresholds are launch-sizing early warnings; tune as real traffic patterns emerge.

Latency alarms are split by traffic regime: the API-wide p99 alarm only
evaluates periods with enough requests for a percentile to be meaningful
(below the floor, p99 equals the slowest single request), while the
per-function `Duration` alarms carry each function's own SLO (public search
tight, admin console loose) and cover low-traffic periods.

---

## Custom Resources

### Database Migrations

| Resource Type | Logical ID | Handler | Notes |
|--------------|------------|---------|-------|
| Custom Resource | `RunMigrations` | `SiutindeiMigrationFunction` | Runs Alembic migrations on stack create/update (triggered by migration hash change) |

**Properties:**
- `MigrationsHash`: SHA256 hash of `backend/db/alembic/versions/` directory
- `SeedHash`: SHA256 hash of `backend/db/seed/seed_data.sql`
- `RunSeed`: `true`

**Rollback caveat:** migrations are forward-only. If a stack update fails
after a new migration has run, the CloudFormation rollback re-invokes
`RunMigrations` with the previous Lambda bundle, which no longer contains
the revision the database is at, and the rollback wedges in
`UPDATE_ROLLBACK_FAILED`. The deploy workflow recovers by calling
`continue-update-rollback --resources-to-skip RunMigrations` when
`RunMigrations` is the failed resource.

### Admin Bootstrap

**Created only if `AdminBootstrapEmail` and `AdminBootstrapTempPassword` parameters are provided.**

| Resource Type | Logical ID | Handler | Notes |
|--------------|------------|---------|-------|
| Custom Resource | `AdminBootstrapResource` | `AdminBootstrapFunction` | Creates admin user in Cognito |

**Properties:**
- `UserPoolId`: Cognito User Pool ID
- `Email`: Admin email address
- `TempPassword`: Temporary password
- `GroupName`: `admin`

---

## CloudFormation Parameters

| Parameter Name | Type | Required | NoEcho | Description |
|----------------|------|----------|---------|-------------|
| `CognitoDomainPrefix` | String | Yes | No | Hosted UI domain prefix |
| `CognitoCallbackUrls` | CommaDelimitedList | Yes | No | OAuth callback URLs |
| `CognitoLogoutUrls` | CommaDelimitedList | Yes | No | OAuth logout URLs |
| `GoogleClientId` | String | Yes | No | Google OAuth client ID |
| `GoogleClientSecret` | String | Yes | Yes | Google OAuth client secret |
| `AppleClientId` | String | Yes | No | Apple Services ID |
| `AppleTeamId` | String | Yes | No | Apple developer team ID |
| `AppleKeyId` | String | Yes | No | Apple Sign In key ID |
| `ApplePrivateKey` | String | Yes | Yes | Apple Sign In private key |
| `AuthEmailFromAddress` | String | Yes | No | SES-verified email for passwordless auth |
| `LoginLinkBaseUrl` | String | No | No | Base URL for magic links (default: empty) |
| `MaxChallengeAttempts` | Number | No | No | Max passwordless auth attempts (default: 3) |
| `PublicApiKeyValue` | String | Yes | Yes | API key for mobile search (min 20 chars) |
| `DeviceAttestationJwksUrl` | String | No | No | JWKS URL for device attestation (default: empty) |
| `DeviceAttestationIssuer` | String | No | No | Expected issuer (default: empty) |
| `DeviceAttestationAudience` | String | No | No | Expected audience (default: empty) |
| `DeviceAttestationFailClosed` | String | No | No | Fail-closed mode (default: `true`, allowed: `true`/`false`) |
| `RunSeedData` | String | No | No | Run seed data after migrations (default: `false`) |
| `FallbackManagerEmail` | String | No | No | Fallback manager email for migration |
| `SupportEmail` | String | No | No | Email to receive manager request notifications |
| `SesSenderEmail` | String | No | No | SES-verified sender email for notifications |
| `OpsAlertsEmail` | String | No | No | Email subscribed to operational CloudWatch alarms (default: empty) |
| `ApiCustomDomainName` | String | No | No | Custom domain for the API (default: empty) |
| `ApiCustomDomainCertificateArn` | String | No | No | ACM certificate ARN for API custom domain |
| `AdminBootstrapEmail` | String | No | No | Admin email for bootstrap (default: empty) |
| `AdminBootstrapTempPassword` | String | No | Yes | Temporary password for bootstrap (default: empty) |

---

## CloudFormation Outputs

| Output Name | Value | Description |
|-------------|-------|-------------|
| `ApiUrl` | API Gateway REST API URL | Base URL for API endpoints |
| `DatabaseSecretArn` | Secrets Manager secret ARN | ARN of database credentials secret |
| `DatabaseProxyEndpoint` | RDS Proxy endpoint | Endpoint for database connections via proxy |
| `UserPoolId` | Cognito User Pool ID | User Pool identifier |
| `UserPoolClientId` | Cognito User Pool Client ID | OAuth client identifier |
| `OrganizationImagesBucketName` | S3 bucket name | Organization media bucket |
| `OrganizationImagesBaseUrl` | S3 bucket URL | Public URL for organization images |
| `AdminImportExportBucketName` | S3 bucket name | Admin import/export JSON bucket |
| `ManagerRequestTopicArn` | SNS topic ARN | Manager request events topic |
| `ManagerRequestQueueUrl` | SQS queue URL | Manager request processing queue |
| `ManagerRequestDLQUrl` | SQS DLQ URL | Failed manager request messages |
| `CognitoCustomDomainCloudFront` | CloudFront distribution | Custom auth domain target (conditional) |
| `ApiCustomDomainTarget` | CNAME target | API custom domain DNS target (conditional) |
| `ApiCustomDomainUrl` | Custom domain URL | API custom domain URL (conditional) |

---

## Resource Dependencies

### Key Dependencies

1. **VPC** → Security Groups → Database/Lambda
2. **Database Secret** → Aurora Cluster → RDS Proxy
3. **Aurora Cluster** → Migration Lambda (direct access)
4. **RDS Proxy** → Application Lambdas (via proxy)
5. **Cognito User Pool** → Identity Providers → User Pool Client
6. **Cognito User Pool** → Auth Lambda Triggers
7. **Lambda Functions** → API Gateway Integrations
8. **API Gateway** → Usage Plan → API Key
9. **Migration Lambda** → Custom Resource (RunMigrations)
10. **Admin Bootstrap Lambda** → Custom Resource (AdminBootstrapResource)

### Conditional Resources

- **VPC**: Created if `EXISTING_VPC_ID` is not set
- **Security Groups**: Created if corresponding `EXISTING_*_SECURITY_GROUP_ID` is not set
- **Database Secret**: Created if `EXISTING_DB_CREDENTIALS_SECRET_NAME` and `EXISTING_DB_CREDENTIALS_SECRET_ARN` are not set
- **Aurora Cluster**: Created if `EXISTING_DB_CLUSTER_IDENTIFIER` is not set
- **RDS Proxy**: Created if `EXISTING_DB_PROXY_NAME` is not set
- **Admin Bootstrap**: Created if `AdminBootstrapEmail` and `AdminBootstrapTempPassword` are provided

---

## Resource Naming Convention

All resources use the prefix: **`lxsoftware-siutindei-`**

Examples:
- VPC: `lxsoftware-siutindei-vpc`
- Security Group: `lxsoftware-siutindei-lambda-sg`
- Database Cluster: `lxsoftware-siutindei-db-cluster`
- User Pool: `lxsoftware-siutindei-user-pool`
- API: `lxsoftware-siutindei-api`

---

## Tagging Coverage

The stack applies two tags at the stack level:

- `Organization= LX Software`
- `Project= Siu Tin Dei`

These tags are inherited by **all taggable resources** created in this
stack, including implicit resources created by CDK (subnets, route
tables, etc.).

Tags are **not guaranteed** on the following:

- Resource types that do not support tagging.
- Imported or existing resources (for example, an existing VPC, DB
  cluster, security groups, or the API access log group).
- Resources created outside the stack lifecycle, such as Lambda log
  groups created on first invocation.
- CDK bootstrap stack resources (CDKToolkit), which are separate from
  this stack.

---

## Resource Retention Policies

The following resources have **RETAIN** deletion policy (survive stack deletion):

- `LambdaSecurityGroup`
- `MigrationSecurityGroup`

All other resources are deleted when the stack is deleted (unless they are imported/existing resources).

---

## Estimated Resource Count

**Minimum (all existing resources imported):**
- ~50-60 resources (Lambdas, IAM roles, API Gateway resources, etc.)

**Maximum (all resources created):**
- ~150-200 resources (includes VPC, subnets, NAT, Aurora, RDS Proxy, all Lambdas with DLQs/KMS, API Gateway, etc.)

---

## Notes

1. **Lambda Log Groups**: Explicitly created by CDK with standard `/aws/lambda/{functionName}` naming and KMS encryption.
2. **API Gateway Access Log Group**: Must exist before deployment (imported, not created).
3. **Existing Resources**: The workflow detects and imports existing VPC, database, and security group resources to avoid recreation.
4. **CDK Bootstrap**: Required once per account/region. The workflow runs `cdk bootstrap` if needed.
5. **Lambda Bundling**: Lambda code is bundled during `cdk synth` using
   Docker or local bundle from `.lambda-build/base`. Python dependencies are
   cached under `.lambda-build/deps-cache` and reused across synth runs until
   `backend/requirements.txt` changes. Cache pruning keeps only the most
   recent dependency cache keys.
