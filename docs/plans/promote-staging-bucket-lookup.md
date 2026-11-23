# Plan: Read the staging bucket inside the promote job

**Status**: Done
**Zone**: red

`promote-public-www.yml` is red. This change is that workflow, the architecture note for the markers, and a test of the workflow shape. No workflow is dispatched.

## Goal

Run [45104912003](https://github.com/lx-software-ltd/siutindei/actions/runs/45104912003) uploaded the production site, then failed on "Record the live production build". The prepare job logged `Skip output 'staging_bucket' since it may contain secret.` The bucket name is `lxsoftware-siutindei-stg-www-<account id>-ap-southeast-1`, and `AWS_ACCOUNT_ID` is a repository secret, so GitHub drops the job output. The promote job then uploaded the markers to `s3:///releases/...`.

The promote job reads `PublicWwwStagingBucketName` from the stack after it assumes the role. The prepare job still uses the name as a step output when it compares catalogue digests.

## Non-goals

- No second production promotion from this change.
- No change to the schedule, the modes, or when a refresh is skipped.
- No account id in git, and no account id in an `if` expression.
- Deploy Public Website stays one job. Its bucket lookup never crosses a job boundary.

## Files

- `.github/workflows/promote-public-www.yml`
- `docs/architecture/public-www.md`
- `tests/test_promote_public_www_markers.py`
- this plan

## Invariants this change preserves

- A schedule still refreshes production. A matching catalogue digest still skips the build.
- A missing production marker still skips. Maintenance still skips the build and still promotes.
- The credentials step in the promote job stays after the production build.
- The account id is `secrets.AWS_ACCOUNT_ID` only.

## Done when

`pytest tests/test_promote_public_www_markers.py` passes. The record step queries `PublicWwwStagingBucketName` and does not read `needs.prepare.outputs.staging_bucket`.

## Rollback

Revert this pull request.

## Open questions

None. The markers for the failed run were not written. The next successful promotion writes them.
