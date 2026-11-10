# Launch checklist (production go-live)

Operator runbook for taking Siu Tin Dei live. Work top-down; each step says
how to verify. Region is `ap-southeast-1` unless stated otherwise
(CloudFront/WAF/ACM for CloudFront are `us-east-1`).

## 1. Data safety (Aurora)

The CDK-managed cluster (`backend/infrastructure/lib/constructs/database.ts`)
sets 14-day backup retention, deletion protection, copy-tags-to-snapshot,
and the RDS HTTP Data API (`enableDataApi: true`). These settings deploy
automatically with the next `lxsoftware-siutindei` stack deploy **only if
the cluster is CDK-created**.

If production imports an existing cluster (any `EXISTING_DB_*` variables set
on the deploy environment), apply the same settings out-of-band:

```bash
aws rds modify-db-cluster \
  --db-cluster-identifier lxsoftware-siutindei-db-cluster \
  --backup-retention-period 14 \
  --deletion-protection \
  --copy-tags-to-snapshot \
  --apply-immediately \
  --region ap-southeast-1

aws rds enable-http-endpoint \
  --resource-arn "$(aws rds describe-db-clusters \
    --db-cluster-identifier lxsoftware-siutindei-db-cluster \
    --query 'DBClusters[0].DBClusterArn' \
    --output text \
    --region ap-southeast-1)" \
  --region ap-southeast-1
```

The lx-software admin stack also re-enables the HTTP endpoint every 15
minutes when `SiutindeiClusterArn` is set. Prefer setting
`enableDataApi: true` on CDK-managed clusters so a product deploy does
not turn it off.

Verify:

```bash
aws rds describe-db-clusters \
  --db-cluster-identifier lxsoftware-siutindei-db-cluster \
  --query 'DBClusters[0].{Backup:BackupRetentionPeriod,Protect:DeletionProtection,Tags:CopyTagsToSnapshot,Http:HttpEndpointEnabled}' \
  --region ap-southeast-1
```

## 2. Snapshot-restore drill (do once before launch)

Confirm backups are actually restorable:

1. Take a manual snapshot:
   `aws rds create-db-cluster-snapshot --db-cluster-identifier lxsoftware-siutindei-db-cluster --db-cluster-snapshot-identifier launch-drill --region ap-southeast-1`
2. Restore it to a throwaway cluster:
   `aws rds restore-db-cluster-from-snapshot --db-cluster-identifier launch-drill-restore --snapshot-identifier launch-drill --engine aurora-postgresql --region ap-southeast-1`
   (add a serverless v2 instance to the restored cluster to query it).
3. Connect and spot-check row counts in `organizations` and `activities`.
4. Delete the drill cluster, instance, and snapshot. Record the time the
   restore took — that is your recovery-time baseline.

## 3. Alarms and alerting

- Deploy the backend stack; the `OpsAlarms` construct creates the
  `lxsoftware-siutindei-ops-alerts` SNS topic and CloudWatch alarms
  (see `docs/architecture/aws-assets-map.md` for the inventory).
- `OpsAlertsEmail` is `support@siutindei.com` in
  `backend/infrastructure/params/production.json`. An SNS email
  subscription starts as `PendingConfirmation`. Changing the parameter
  replaces the subscription, and alarms stay silent until that address
  opens the confirmation link.
- Verify: `aws sns list-subscriptions-by-topic --topic-arn <ops-alerts-arn> --region ap-southeast-1`
  shows the email subscription with a `SubscriptionArn` (not
  `PendingConfirmation`).
- Optional smoke: `aws cloudwatch set-alarm-state --alarm-name lxsoftware-siutindei-api-5xx-alarm --state-value ALARM --state-reason "launch drill" --region ap-southeast-1`
  and confirm the email arrives, then set it back to `OK`.

## 4. Email (SES)

- Confirm SES production access (out of sandbox) in `ap-southeast-1`.
- Sending uses the verified `siutindei.com` domain identity (owned by the
  lx-software stack). Addresses: `hello@siutindei.com`
  (`AuthEmailFromAddress`), `no-reply@siutindei.com` (`SesSenderEmail`,
  also the manager-request sender), and `support@siutindei.com`
  (`SupportEmail` and `OpsAlertsEmail`). Address-level identities are not
  required. Confirm the domain:
  `aws ses get-identity-verification-attributes --identities siutindei.com --region ap-southeast-1`
  shows `VerificationStatus` `Success`.
- Do not delete the `siutindei.com` SES identity from the lx-software stack.
  Siutindei mail stops if it goes.
- Send a test login (email OTP) end-to-end from the admin web login screen.

## 5. GitHub Environments (secrets and variables)

On the **production** environment:

- Secrets: `CDK_PARAM_GOOGLE_CLIENT_SECRET`, `CDK_PARAM_APPLE_PRIVATE_KEY`,
  `CDK_PARAM_PUBLIC_API_KEY_VALUE`,
  `CDK_PARAM_ADMIN_BOOTSTRAP_TEMP_PASSWORD`,
  `CDK_PARAM_GOOGLE_PLACES_API_KEY`,
  `CDK_PARAM_OPENROUTER_API_KEY`,
  `CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN`, and
  `CDK_PARAM_PUBLIC_WWW_ORIGIN_VERIFY`. Until `CDK_PARAM_OPENROUTER_API_KEY`
  is set, the `openrouter-api-key` secret holds `pending` and category and
  enrichment scans cannot call the model. Generate
  the attestation token and origin-verify secret with
  `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` and store
  each value once. The promote workflow reads the attestation token from
  `CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN`; do not create a second copy.
  Set secret `NEXT_PUBLIC_SEARCH_API_KEY` to the live mobile search API key.
  Search calls the website origin from `NEXT_PUBLIC_SITE_ORIGIN`. Delete
  the `NEXT_PUBLIC_SEARCH_API_BASE_URL` repository variable once that
  behavior is on `main`. Promote checks out `main` and no longer reads the
  variable. Leave it in place while `main` still passes it into the build.
  A local `.env` may still set it to call a different origin.
- The website attestation parameters default to empty. A backend deploy
  before those two secrets exist succeeds and leaves website search closed.
  Set the secrets, deploy the API stack and the public website stack, then
  promote. Promotion before that deploy ships a token the authorizer and
  CloudFront do not know yet.
- To rotate, set `CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN_PREVIOUS` and
  `CDK_PARAM_PUBLIC_WWW_ORIGIN_VERIFY_PREVIOUS` to the values currently in
  production, put the new values in `CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN`
  and `CDK_PARAM_PUBLIC_WWW_ORIGIN_VERIFY`, and deploy the API stack first.
  Then deploy the public website stack and promote. After both are serving
  the new values, clear the previous secrets and deploy the API stack again.
- Cloudflare origin lock (applied): `CDK_PARAM_PUBLIC_WWW_EDGE_VERIFY`
  and `CDK_PARAM_PUBLIC_WWW_STAGING_EDGE_VERIFY`
  (`[A-Za-z0-9+/=_-]`, 32+ chars; `token_urlsafe(48)` fits). Production
  uses the Cloudflare transform rule (`PUBLIC_WWW_EDGE_VERIFY_SECRET` in
  `scripts/cloudflare/edge_policy.py apply`). Staging uses the Worker
  binding `PUBLIC_WWW_STAGING_EDGE_VERIFY_SECRET` on
  `siutindei-www-staging-redirect-allowlist`. Empty would leave the check
  off and re-attach the CloudFront WAF. `…_PREVIOUS` variants exist for
  rotation. Clearing a GitHub secret does not disable the lock; the
  deploy workflow skips empty values unless the parameter is in
  `pass_empty_params`.
- Variables: `APPLE_TEAM_ID`, `CDK_PARAM_FILE` pointing at
  `params/production.json`. `SEARCH_AREA_SCOPE` is optional. Leave it
  unset to show every Hong Kong neighbourhood. Set a comma-separated
  list of region ids, district slugs, and neighbourhood slugs to limit
  public search. The same variable is read by the backend deploy and
  by the public website build, so set it at repository level or on
  both the production and staging environments. Clearing it takes
  effect on the next backend deploy because `SearchAreaScope` is
  passed even when empty. A website promote or staging deploy is
  also required before the search controls match.

On the **staging** environment (public www):

- `STAGING_SEARCH_DATA_ENABLED=true` only while staging should serve the
  fixture. Removing the variable keeps the fixture on, because the workflow
  defaults it to `true`. It may live as a repository variable; a value on
  the staging environment overrides it. Set it to `false` to serve Aurora
  through `https://www-staging.siutindei.com`. Only then does the staging
  deploy pass `NEXT_PUBLIC_SEARCH_API_KEY` and
  `CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN` into the build and the smoke
  probe. A fixture build leaves both empty so they are not inlined.
  Those secrets must be repository secrets, or set on the staging
  environment as well. The build-env contract fails when either is empty.

## 6. DNS / certificates

`api.siutindei.com`, `auth.siutindei.com`, and `admin.siutindei.com`
are Cloudflare CNAMEs with the proxy **disabled** (grey cloud). The
apex `siutindei.com` is orange-cloud (proxied, origin-locked).
`www.siutindei.com` is an orange-cloud 301 to the apex.
`www-staging.siutindei.com` is orange-cloud so the allow-list Worker
can run and set the origin-lock header.

| Record | Target source |
|---|---|
| `siutindei.com` | public-www CloudFront distribution (canonical, proxied, origin-locked) |
| `www.siutindei.com` | 301 → `https://siutindei.com/$1` (Cloudflare Worker) |
| `api.siutindei.com` | `ApiSecondaryCustomDomainTarget` stack output |
| `auth.siutindei.com` | `CognitoCustomDomainCloudFront` stack output |
| `admin.siutindei.com` | admin-web CloudFront distribution |
| `www-staging.siutindei.com` | public-www staging distribution, proxied behind the IP allow-list Worker and origin-locked |

The apex proxy and origin lock from
[`docs/plans/cloudflare-edge-protection.md`](../plans/cloudflare-edge-protection.md)
are live. Direct `d2zpx4ub70d0qj.cloudfront.net` and
`d2y0sgtf8djbdr.cloudfront.net` return 403. Cloudflare SSL mode is
`strict`.

To roll the apex back to grey, disable the origin lock first.
`PublicWwwEdgeVerifySecret` and `PublicWwwStagingEdgeVerifySecret` are
not in `pass_empty_params`, so emptying
`CDK_PARAM_PUBLIC_WWW_EDGE_VERIFY` or
`CDK_PARAM_PUBLIC_WWW_STAGING_EDGE_VERIFY` and redeploying leaves the
previous CloudFormation value in place. Update
`lxsoftware-siutindei-public-www` in the CloudFormation console and set
the edge-verify parameters to empty. That removes the header check and
re-attaches the WAF. Then clear those GitHub secrets so a later deploy
does not put them back (an empty secret is skipped, so the console's
empty value stays). Confirm
`curl -sI https://d2zpx4ub70d0qj.cloudfront.net/en/ -H 'Host: siutindei.com'`
returns 200, and the same for `d2y0sgtf8djbdr.cloudfront.net` with
`Host: www-staging.siutindei.com`. Only then run
`edge_policy.py apply --yes --section dns --proxied false`. Greying the
apex while the lock is still on refuses direct visitors until the stack
update finishes.

Verify each with `curl -sI https://<domain>` (expect 200/301, valid cert).

## 7. Security posture

- `DeviceAttestationFailClosed` is pinned to `"true"` in
  `params/production.json`. After deploy, confirm the device-attestation
  authorizer Lambda (`DeviceAttestationAuthorizer`) env var:
  `aws lambda get-function-configuration --function-name <attestation-authorizer-fn> --query 'Environment.Variables.ATTESTATION_FAIL_CLOSED' --region ap-southeast-1`.
- Confirm the admin web CloudFront distribution still has the shared
  WAF WebACL attached (`webAclId` is `WafWebAclArn`; that stack requires
  the ARN). The public website distributions do not, while their origin
  locks are on: `WafWebAclArn` is unused on a locked distribution.
  Cloudflare's custom rules and rate limit cover the proxied public
  hosts.

## 8. Public website go-live

1. Deploy to staging (`deploy-public-www.yml`); smoke checks run
   automatically after the deploy.
2. Run the Lighthouse workflow with `page_paths` set to full staging URLs
   (for example `https://www-staging.siutindei.com/en/`); bare
   paths audit a local build. Investigate any score regression before
   promoting.
3. Verify legal pages render (`/en/privacy`, `/zh-HK/privacy`, `/en/terms`)
   and the analytics consent banner appears when GTM/Meta Pixel IDs are
   configured. Set GitHub Environment `NEXT_PUBLIC_GTM_ID` (`GTM-…` only)
   and `NEXT_PUBLIC_GTM_ALLOWED_HOSTS` (production:
   `siutindei.com,www.siutindei.com`; staging should also include
   `www-staging.siutindei.com`). Confirm
   `NEXT_PUBLIC_WHATSAPP_URL` is set. Rebuild/promote after changing
   `NEXT_PUBLIC_*` — they are build-time. After consent: decline must not
   load `gtm.js`; accept loads `gtm.js?id=GTM-…`. GTM Preview should show
   All Pages → GA4 Config, activity → `view_item`, WhatsApp →
   `generate_lead`.
4. Promote with `promote-public-www.yml` (`promotion_mode=latest_staging`,
   or `promotion_mode=release_id` with the `release_id` input).
   The API stack and public website stack must already be deployed with
   non-empty `CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN` and
   `CDK_PARAM_PUBLIC_WWW_ORIGIN_VERIFY`. Empty defaults leave website search
   closed.
5. Post-promote: spot-check production search, an activity detail page, and
   both locales.

## 9. Mobile beta (after web go-live)

- Follow `docs/deployment/android-play-store.md` and
  `docs/deployment/ios-testflight.md`.
- Store privacy questionnaires: use `docs/legal/store-disclosures.md`.
