# Plan: Switch the admin site to s3-cloudfront-deploy

**Status**: In progress
**Zone**: red

## Goal

Replace the admin deploy script with `s3-cloudfront-deploy` profile `next-export`. The dry run matched twice: `45142775654` and `45142938340`, both with 96 planned S3 changes. evolvesprouts was switched first and its post-switch deploy succeeded.

## Non-goals

- No change to the local script `scripts/deploy/deploy-admin-web.sh`.
- No Amplify release. That step was skipped on the matching runs.

## Files

`.github/workflows/deploy-admin-web.yml`, this plan.

## Invariants this change preserves

- The build still comes from `apps/admin_web/out`.
- The bucket and distribution still come from `lxsoftware-siutindei-admin-web`.
- The sync is still `aws s3 sync --delete` followed by a CloudFront invalidation.
- The actions pin stays `ffde04dca3c78b1ccb8739f4d3a23f728ac7a05f`.

## Done when

The workflow calls `s3-cloudfront-deploy` and the dry-run comparison is gone. `repository_dispatch` type `deploy-admin-web` is added so the post-switch deploy can run; the path filter does not include the workflow file. After merge, one Deploy Admin Web succeeds, and `https://admin.siutindei.com/` still returns HTTP 200, `content-type: text/html`, `server: AmazonS3`, and `x-amz-server-side-encryption: AES256` through CloudFront.

## Rollback

Revert the pull request and run Deploy Admin Web again. The script is still in the repository.
