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
- `OpsAlertsEmail` is set to `support@lx-software.com` in
  `backend/infrastructure/params/production.json`. After the first deploy,
  **confirm the SNS subscription** from the confirmation email sent to that
  address — alarms are silent until confirmed.
- Verify: `aws sns list-subscriptions-by-topic --topic-arn <ops-alerts-arn> --region ap-southeast-1`
  shows the email subscription with a `SubscriptionArn` (not
  `PendingConfirmation`).
- Optional smoke: `aws cloudwatch set-alarm-state --alarm-name lxsoftware-siutindei-api-5xx-alarm --state-value ALARM --state-reason "launch drill" --region ap-southeast-1`
  and confirm the email arrives, then set it back to `OK`.

## 4. Email (SES)

- Confirm SES production access (out of sandbox) in `ap-southeast-1`.
- Verified identities must include: `hello@lx-software.com`
  (`AuthEmailFromAddress`), `no-reply@lx-software.com` (`SesSenderEmail`),
  and `support@lx-software.com` (`SupportEmail`).
- Verify: `aws ses get-identity-verification-attributes --identities hello@lx-software.com no-reply@lx-software.com support@lx-software.com --region ap-southeast-1`.
- Send a test login (email OTP) end-to-end from the admin web login screen.

## 5. GitHub Environments (secrets and variables)

On the **production** environment:

- Secrets: `CDK_PARAM_GOOGLE_CLIENT_SECRET`, `CDK_PARAM_APPLE_PRIVATE_KEY`,
  `CDK_PARAM_PUBLIC_API_KEY_VALUE`,
  `CDK_PARAM_ADMIN_BOOTSTRAP_TEMP_PASSWORD`,
  `CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN`, and
  `CDK_PARAM_PUBLIC_WWW_ORIGIN_VERIFY`. Generate the last two with
  `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` and store
  each value once. The promote workflow reads the attestation token from
  `CDK_PARAM_PUBLIC_WWW_ATTESTATION_TOKEN`; do not create a second copy.
  Also set variable `NEXT_PUBLIC_SEARCH_API_BASE_URL` to `https://siutindei.com`
  and secret `NEXT_PUBLIC_SEARCH_API_KEY` to the live mobile search API key.
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
- Variables: `APPLE_TEAM_ID`, `CDK_PARAM_FILE` pointing at
  `params/production.json`.

On the **staging** environment (public www):

- `STAGING_SEARCH_DATA_ENABLED=true` only while staging should serve the
  fixture. **Set to `false` (or remove) when staging should exercise the live
  API before launch.**

## 6. DNS / certificates

CloudFront aliases are Cloudflare CNAMEs with the proxy **disabled**
(grey cloud). `www.siutindei.com` and the legacy
`siutindei-www.lx-software.com` hostname are orange-cloud 301s to the apex.

| Record | Target source |
|---|---|
| `siutindei.com` | public-www CloudFront distribution (canonical) |
| `www.siutindei.com` | 301 → `https://siutindei.com/$1` (Cloudflare Worker) |
| `siutindei-www.lx-software.com` | 301 → `https://siutindei.com/$1` (Cloudflare Worker) |
| `siutindei-api.lx-software.com` | `ApiCustomDomainTarget` stack output |
| `siutindei-auth.lx-software.com` | `CognitoCustomDomainCloudFront` stack output |
| `siutindei.lx-software.com` | admin-web CloudFront distribution |
| `siutindei-www-staging.lx-software.com` | public-www staging distribution |

Verify each with `curl -sI https://<domain>` (expect 200/301, valid cert).

## 7. Security posture

- `DeviceAttestationFailClosed` is pinned to `"true"` in
  `params/production.json`. After deploy, confirm the search Lambda env var:
  `aws lambda get-function-configuration --function-name <search-fn> --query 'Environment.Variables.ATTESTATION_FAIL_CLOSED' --region ap-southeast-1`.
- Confirm the WAF WebACL is associated with the CloudFront distributions
  (`WafWebAclArn` in params).

## 8. Public website go-live

1. Deploy to staging (`deploy-public-www.yml`); smoke checks run
   automatically after the deploy.
2. Run the Lighthouse workflow against staging; investigate any score
   regression before promoting.
3. Verify legal pages render (`/en/privacy`, `/zh-HK/privacy`, `/en/terms`)
   and the analytics consent banner appears when GTM/Meta Pixel IDs are
   configured. Set GitHub Environment `NEXT_PUBLIC_GTM_ID` (`GTM-…` only)
   and `NEXT_PUBLIC_GTM_ALLOWED_HOSTS` (production:
   `siutindei.com,www.siutindei.com`; staging should also include
   `siutindei-www-staging.lx-software.com`). Confirm
   `NEXT_PUBLIC_WHATSAPP_URL` is set. Rebuild/promote after changing
   `NEXT_PUBLIC_*` — they are build-time. After consent: decline must not
   load `gtm.js`; accept loads `gtm.js?id=GTM-…`. GTM Preview should show
   All Pages → GA4 Config, activity → `view_item`, WhatsApp →
   `generate_lead`.
4. Promote with `promote-public-www.yml`
   (`PUBLIC_WWW_PROMOTE_RELEASE_ID` = the staging release to promote).
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
