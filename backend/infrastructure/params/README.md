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
(`.github/workflows/deploy-public-www.yml`,
`.github/workflows/promote-public-www.yml`).

| Parameter | Purpose |
|-----------|---------|
| `PublicWwwDomainName` | Production CloudFront alias (e.g. `siutindei.com`). |
| `PublicWwwCertificateArn` | ACM cert ARN in **us-east-1** that covers the production alias. |
| `PublicWwwStagingDomainName` | Staging CloudFront alias (e.g. `siutindei-www-staging.lx-software.com`). |
| `PublicWwwStagingCertificateArn` | ACM cert ARN in **us-east-1** that covers the staging alias. |
| `WafWebAclArn` | (Optional) us-east-1 WAF WebACL ARN; reuse the admin-web ACL. |

Static-export branding defaults (site name, tagline, contact email,
WhatsApp URL, and WhatsApp display number) live in
`apps/public_www/build-env.defaults.json` and are **not** CDK parameters.
CI reads the email via `scripts/deploy/resolve-public-www-build-env.sh`.
The full site and the maintenance holding page use those same contacts.

Before the first `cdk deploy`, ensure the ACM certificate listed in
`PublicWwwCertificateArn`/`PublicWwwStagingCertificateArn` includes the
public website hostnames as Subject Alternative Names. Production uses a
dedicated `us-east-1` certificate covering `siutindei.com` and
`*.siutindei.com`. Staging still uses the shared `lx-software.com`
certificate for `siutindei-www-staging.lx-software.com`. Extend the
certificate SANs if a hostname is not yet covered before deploying.
