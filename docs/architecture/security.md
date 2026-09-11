# Security Guidelines

This document outlines security best practices and requirements for the Siu Tin Dei project. All contributors must follow these guidelines.

## Table of Contents

- [Secrets Management](#secrets-management)
- [Logging Security](#logging-security)
- [Authentication Security](#authentication-security)
- [API Security](#api-security)
- [Infrastructure Security](#infrastructure-security)
- [Code Review Checklist](#code-review-checklist)
- [Reporting Security Issues](#reporting-security-issues)

---

## Secrets Management

### DO NOT

- **Never** hardcode secrets, API keys, passwords, or tokens in source code
- **Never** commit `.env` files, keystores, or credential files
- **Never** log secrets or tokens (even partially)
- **Never** include secrets in error messages returned to clients

### DO

- Use AWS Secrets Manager for database credentials
- Use GitHub Secrets for CI/CD sensitive values
- Use CDK parameters with `noEcho: true` for secrets
- Use environment variables at runtime

### Example - CDK Parameter for Secrets

```typescript
const secretParam = new cdk.CfnParameter(this, "MySecret", {
  type: "String",
  noEcho: true,  // REQUIRED for secrets
  description: "Description without revealing the secret type",
});
```

---

## Logging Security

### PII Protection

Email addresses and other personally identifiable information (PII) must be masked in logs to comply with privacy regulations (GDPR, etc.).

### DO NOT

```python
# BAD - exposes email in logs
logger.info(f"User signed up: {email}")
logger.warning(f"Failed login for {user_email}")
```

### DO

```python
from app.utils.logging import mask_email, mask_pii, hash_for_correlation

# GOOD - masks PII
logger.info(f"User signed up: {mask_email(email)}")  # Output: jo***@***.com

# GOOD - use hash for correlation
correlation_id = hash_for_correlation(email)
logger.info(f"Processing request", extra={"correlation_id": correlation_id})

# GOOD - mask other PII
logger.info(f"User ID: {mask_pii(user_id)}")  # Output: abc1***
```

### Available Utilities

| Function | Purpose | Example Output |
|----------|---------|----------------|
| `mask_email(email)` | Mask email addresses | `jo***@***.com` |
| `mask_pii(value)` | Mask any PII | `abc1***` |
| `hash_for_correlation(value)` | Hash for log correlation | `a1b2c3d4e5f6` |

### Print Statements

**Never use `print()` in production code.** Always use structured logging:

```python
# BAD
print(f"Processing user {user_id}")

# GOOD
from app.utils.logging import configure_logging, get_logger
configure_logging()
logger = get_logger(__name__)
logger.info("Processing user", extra={"user_id_masked": mask_pii(user_id)})
```

---

## Authentication Security

### OTP/Code Generation

**Always use cryptographically secure random for security tokens.**

```python
# BAD - predictable, not secure
import random
code = "".join(random.choice(string.digits) for _ in range(6))

# GOOD - cryptographically secure
import secrets
code = "".join(secrets.choice(string.digits) for _ in range(6))
```

### Device Attestation

The device attestation authorizer has two modes:

| Mode | `ATTESTATION_FAIL_CLOSED` | Behavior |
|------|---------------------------|----------|
| **Production** | `true` (default) | Denies requests when attestation is not configured |
| **Development** | `false` | Allows requests without attestation |

**WARNING:** Always use `ATTESTATION_FAIL_CLOSED=true` in production environments.

### CDK Configuration

```typescript
const deviceAttestationFailClosed = new cdk.CfnParameter(
  this,
  "DeviceAttestationFailClosed",
  {
    type: "String",
    default: "true",  // Secure default
    allowedValues: ["true", "false"],
    description: "SECURITY: Must be 'true' in production.",
  }
);
```

### Partner API keys

The `/v1/partner/*` endpoints are authenticated with custom API keys sent
in the `x-partner-key` header:

- Keys are generated with the `secrets` module
  (`stk_<43 urlsafe characters>`) and only a **SHA-256 hash** is stored in
  the `api_keys` table. The plaintext is returned once at creation and
  never logged.
- A dedicated in-VPC Lambda request authorizer
  (`PartnerApiKeyAuthorizerFunction`) validates the hash against the
  database and rejects revoked or expired keys. Authorizer results are
  cached for 5 minutes, which bounds how long a revoked key keeps working.
- Keys carry a scope (`read` = GET only, `crud` = full CRUD) and an
  optional organization scope. Because the cached Allow policy covers all
  partner routes, **scope and organization enforcement is re-checked in
  the handlers** (defense in depth, same pattern as the Cognito group
  checks).
- Writes performed with a key are attributed to `api-key:<id>` in the
  audit log.
- Admins manage keys via `/v1/admin/api-keys` (generate, list, revoke);
  revocation is a soft delete so the audit trail is preserved.

### JWT validation

Authorizers may decode a JWT payload **without** verifying the signature
so they can read the `iss` claim and select the correct JWKS URL. Those
unverified claims are **not** trusted. `decode_and_verify_token()` in
`backend/src/app/auth/jwt_validator.py` then verifies the signature
(RS256), issuer, and expiry against that JWKS before any claim is used.

JWT authorizers (device attestation, admin, manager, user) run **outside
the VPC** so they can fetch public JWKS. The VPC has no NAT Gateway.
In-VPC Lambdas call Cognito through the AWS/HTTP proxy instead — see
[`decisions.md`](./decisions.md#aws--http-proxy) and
[`lambdas.md`](./lambdas.md).

### Edge caching of the public search endpoint

`GET /v1/activities/search` is cached at the CloudFront edge via the
public-website distribution (see
[`public-www.md`](./public-www.md#search-api-edge-caching)). On a cache **hit**,
CloudFront serves the response without re-invoking the origin, so the
per-request `x-api-key` and `x-device-attestation` checks are **not** enforced
for cached entries. This is acceptable because:

- These controls are **anti-abuse / rate-limiting**, not data protection — the
  search results are public.
- Only the exact `/v1/activities/search` path is proxied; admin endpoints
  (`/v1/admin/*`) are never reachable through the website domain.
- Edge abuse protection is provided by the CloudFront WAF WebACL.
- On a cache **miss**, the request is forwarded to the API Gateway origin with
  the auth headers intact, where the device-attestation authorizer and API key
  are enforced as normal.

The cache key includes all query strings but **no** request headers, so a
single cached response is shared across callers (no per-token cache
fragmentation, no leakage of caller-specific data).

---

## API Security

### CORS Configuration

**Never use `Cors.ALL_ORIGINS` in production.** Always restrict to specific allowed origins.

```typescript
// BAD - allows any website to make requests
defaultCorsPreflightOptions: {
  allowOrigins: apigateway.Cors.ALL_ORIGINS,
}

// GOOD - restrict to specific origins
const corsAllowedOrigins = new cdk.CfnParameter(this, "CorsAllowedOrigins", {
  type: "CommaDelimitedList",
  description: "SECURITY: Never use '*' in production.",
});

defaultCorsPreflightOptions: {
  allowOrigins: corsAllowedOrigins.valueAsList,
}
```

### Default Allowed Origins

If no origins are configured, defaults to mobile app schemes only:
- `capacitor://localhost`
- `ionic://localhost`
- `http://localhost` (for development)

### Input Validation

Always validate and sanitize user input:

```python
from app.utils.validators import validate_uuid, validate_email, sanitize_string

# Validate UUIDs
entity_id = validate_uuid(request_id, field_name="id")

# Validate emails
email = validate_email(user_email)

# Sanitize strings with length limits
description = sanitize_string(user_input, max_length=1000)
```

### Error Responses

**Never expose internal error details to clients.**

```python
# BAD - exposes internal details
return {"error": str(exception), "traceback": traceback.format_exc()}

# GOOD - generic error message
logger.exception("Internal error")  # Log details internally
return {"error": "Internal server error"}  # Generic response to client
```

---

## Infrastructure Security

### IAM Permissions

- Use least-privilege IAM roles
- Use OIDC for GitHub Actions (no long-lived AWS keys)
- Scope permissions to specific resources

### Public asset buckets

`OrganizationImagesBucket` (`lxsoftware-siutindei-org-media-{account}-{region}`)
is **intentionally public** so organization logos and photos can be
served directly. This is a product decision, not an accidental exposure.

Mitigations already in place:

- `BLOCK_ACLS` — public read is bucket-policy only, not object ACLs
- `enforceSSL` and versioning
- Access logging to `OrganizationImagesLogBucket`

Public-www and admin-web static assets use CloudFront (OAI), not this
bucket. Serving org media through CloudFront + OAC is an optional later
enhancement (private bucket, edge cache), not a current security
regression. See [`aws-assets-map.md`](./aws-assets-map.md) and
`backend/infrastructure/.checkov.yaml`.

### Database Security

- Always use SSL: `sslmode=require`
- Prefer IAM authentication for RDS Proxy
- Use separate database users for different access levels:
  - `siutindei_app` - read-only for search
  - `siutindei_admin` - read-write for admin
- The CDK-managed Aurora cluster enables the RDS HTTP Data API
  (`enableDataApi: true`). That is an AWS HTTPS API (`rds-data`)
  authenticated with IAM plus Secrets Manager, not a public SQL
  port. Product Lambdas must keep using RDS Proxy; do not grant
  `rds-data:*` to those functions. The lx-software Executive Board
  `AdminApiFn` is the intended Data API caller.
- `POST /v1/listing-events` is public telemetry (API key + device
  attestation, same anti-abuse model as search). Accept only
  enumerated event types; do not persist search terms, names, or
  other PII. CloudFront caches this path never. The board already
  has GA4; do not copy GA4 into Aurora.
- If importing an existing Secrets Manager credential secret encrypted
  with a customer-managed KMS key, ensure Lambda roles can decrypt it
  (set `EXISTING_DB_CREDENTIALS_SECRET_KMS_KEY_ARN` or use auto-detect).

### Dependency vulnerability handling

- Dependabot version updates cover GitHub Actions, pip (`/backend`),
  pub (`/apps/siutindei_app`), and npm
  (`/backend/infrastructure`, `/apps/public_www`, `/apps/admin_web`).
- Public-www production Highs are gated by `npm run audit:deps:prod`
  (`npm audit --omit=dev --audit-level=high`).
- `extract-zip` (GHSA-jmr9-qjv8-65gv) is a dev-only transitive of
  `@lhci/cli` / Lighthouse 12. There is no patched release; Dependabot
  ignores it in `/apps/public_www` until LHCI ships Lighthouse 13+.
  Do not run `npm audit fix --force` (it downgrades `@lhci/cli` to 0.6.1).
- Bundled `aws-cdk-lib` copies of `minimatch` are replaced at
  `postinstall`. Keep `aws-cdk-lib` at 2.265.0+ so the bundled
  `brace-expansion` is 5.0.9 (GHSA-rgw5-rvv9-x895). `npm overrides`
  cannot replace `inBundle` packages.

### Semgrep OSS

SAST runs in `.github/workflows/semgrep.yml` (not `security.yml`). GitHub
Code Scanning's Semgrep OSS setup looks for that path; embedding the job
only in `security.yml` left the tool-status page at "1 configuration not
found". Packs: `p/python`, `p/security-audit`, `p/secrets`,
`p/owasp-top-ten`. SARIF category stays `semgrep`.
`--exclude-rule` skips `dynamic-urllib-use-detected` (`cfn_response.py`
HTTPS/.amazonaws.com URL check) and `gha-curl-pipe-shell` (false-positive
Bash parse of GitHub `${{ }}` in workflow `run:` blocks; those SARIF
warnings were surfacing on the Code Scanning tool-status page).

### Gitleaks Secret Scanning

Secret Scanning in `.github/workflows/security.yml` runs the MIT-licensed
`gitleaks` CLI (pinned version + SHA-256). It does not use
`gitleaks/gitleaks-action`, which requires a `GITLEAKS_LICENSE` on
organization repositories. Dependabot `pull_request` runs cannot read
Actions secrets, so the licensed action failed every Dependabot PR with
"missing gitleaks license" even after the secret was wired in (#444).

### GitHub Workflow Permissions

Always use minimal permissions:

```yaml
permissions:
  contents: read  # Minimum required
  id-token: write  # Only if using OIDC
```

---

## Code Review Checklist

Before approving any PR, verify:

### Secrets
- [ ] No hardcoded secrets, API keys, or passwords
- [ ] New secrets use appropriate storage (Secrets Manager, GitHub Secrets)
- [ ] CDK parameters for secrets have `noEcho: true`

### Logging
- [ ] No PII (emails, names, etc.) logged without masking
- [ ] No `print()` statements in production code
- [ ] Error messages don't expose internal details

### Authentication
- [ ] Security tokens use `secrets` module, not `random`
- [ ] Device attestation uses fail-closed mode in production

### API
- [ ] CORS restricted to specific origins (not `ALL_ORIGINS`)
- [ ] Input is validated before processing
- [ ] Error responses don't leak internal details

### Infrastructure
- [ ] IAM permissions follow least-privilege
- [ ] Database connections use SSL
- [ ] Workflow permissions are minimal

---

## Reporting Security Issues

If you discover a security vulnerability, please:

1. **Do not** create a public GitHub issue
2. Contact the maintainers privately
3. Provide details about the vulnerability and steps to reproduce

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [AWS Security Best Practices](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html)
- [GDPR Logging Requirements](https://gdpr.eu/article-32-security-of-processing/)
