# CDK parameter files

Use `production.json` as a template for CDK parameters.

## Local deploy

```bash
cd backend/infrastructure
export CDK_PARAM_FILE=params/production.json
npx cdk deploy --require-approval never
```

## GitHub Actions

Set the repository variable `CDK_PARAM_FILE` to the path you want CI to use
(`params/production.json` by default).

> Keep secrets out of the repo. For production, use a private parameter file
> stored outside of git or generated in CI from secrets.

## Public Website (`PublicWwwStack`)

The public website stack provisions both production and staging environments
in a single `lxsoftware-siutindei-public-www` CloudFormation stack.

Deploy the CDK stack via GitHub Actions **Deploy Backend** (`public website`
or `all stacks`). Deploy static site artifacts with
**Deploy Public Website Staging** / **Promote Public Website Release**
(`.github/workflows/deploy-public-www-staging.yml`,
`.github/workflows/promote-public-www.yml`).

| Parameter | Purpose |
|-----------|---------|
| `PublicWwwDomainName` | Production CloudFront alias (e.g. `siutindei.com`). |
| `PublicWwwCertificateArn` | `<FROM_GITHUB_SECRET: CDK_PARAM_PUBLIC_WWW_CERTIFICATE_ARN>`, ACM in **us-east-1** for the production alias. |
| `PublicWwwStagingDomainName` | Staging CloudFront alias (e.g. `www-staging.siutindei.com`). |
| `PublicWwwStagingCertificateArn` | `<FROM_GITHUB_SECRET: CDK_PARAM_PUBLIC_WWW_STAGING_CERTIFICATE_ARN>`, ACM in **us-east-1** for the staging alias. |
| `WafWebAclArn` | `<FROM_GITHUB_SECRET: CDK_PARAM_WAF_WEB_ACL_ARN>`, the us-east-1 WAF WebACL ARN. Empty keeps the previous value only when the parameter is omitted; this key is still sent when the secret is empty. |
| `SearchApiProxyOriginDomain` | API custom domain CloudFront forwards `/v1/activities/search` to. |
| `PublicWwwOriginVerifySecret` | Shared secret CloudFront sends to the API origin as `X-Origin-Verify`; the API authorizer checks it. Empty disables the header; otherwise at least 32 characters. CI passes it to both the API and public website stacks. Store it in GitHub secret `CDK_PARAM_PUBLIC_WWW_ORIGIN_VERIFY`. |
| `PublicWwwOriginVerifySecretPrevious` | (API stack only) Previous value the authorizer still accepts during rotation. GitHub secret `CDK_PARAM_PUBLIC_WWW_ORIGIN_VERIFY_PREVIOUS`. |

Static-export branding defaults (site name, tagline, contact email,
WhatsApp URL, and WhatsApp display number) live in
`apps/public_www/build-env.defaults.json` and are **not** CDK parameters.
CI reads the email via `scripts/deploy/resolve-public-www-build-env.sh`.
The full site and the maintenance holding page use those same contacts.

Before the first `cdk deploy`, ensure the ACM certificate listed in
`PublicWwwCertificateArn`/`PublicWwwStagingCertificateArn` includes the
public website hostnames as Subject Alternative Names. Production uses a
dedicated `us-east-1` certificate covering `siutindei.com` and
`*.siutindei.com`. Staging uses the same certificate for
`www-staging.siutindei.com`. Extend the
certificate SANs if a hostname is not yet covered before deploying.

## API custom domains (`ApiStack`)

| Parameter | Purpose |
|-----------|---------|
| `ApiCustomDomainName` / `ApiCustomDomainCertificateArn` | Production API host `api.siutindei.com`. The certificate value is the placeholder `<FROM_GITHUB_SECRET: CDK_PARAM_API_SECONDARY_CUSTOM_DOMAIN_CERTIFICATE_ARN>` in **ap-southeast-1**. Both must be set; either empty creates nothing. The domain construct ids are historical and must not change. |
| `ApiDisableExecuteApiEndpoint` | `true` refuses the raw execute-api hostname. It only applies while the custom domain is configured. |

When the custom domain exists, `ApiCustomDomainUrl` is the endpoint
`build_amplify_config.py` hands to the mobile app. The sequence is in
`docs/plans/siutindei-domain-consolidation.md`.

## Catalog review (`ApiStack`)

| Parameter | Purpose |
|-----------|---------|
| `OrgReviewGateEnabled` | `true` hides organizations that are not `approved` from public and partner search. The CDK default is `false`. Production sets `true`. |
