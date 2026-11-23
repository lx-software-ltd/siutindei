# Plan: Keep rebuilt Lambda bundles out of the source hash

**Status**: In progress
**Zone**: yellow

## Goal

Stop Deploy Backend from updating every Lambda function when the source has not changed. `PythonLambda` hashes `backend/` with `AssetHashType.SOURCE`. `backend/.lambda-build` is recreated before synth. Bootstrap also rewrites `backend/infrastructure/cdk.out` before the deploy hash, and that directory contains zip timestamps. Exclude both. A pattern without a leading `**` does not match a directory under `infrastructure/`.

## Non-goals

- No change to the bundle contents or to which files are copied into the function.
- No change to evolvesprouts. This is the siutindei construct.

## Files

`backend/infrastructure/lib/constructs/python-lambda.ts`, this plan.

## Invariants this change preserves

- The function still publishes the prebuilt bundle from `.lambda-build`.
- A change under `backend/lambda` or `backend/src` still changes the hash.

## Done when

The exclude list contains `.lambda-build/**`, `**/cdk.out/**`, `**/node_modules/**`, `**/dist/**`, and `**/build/**`. The next source-only deploy still updates the functions once, because the hash changes. A later deploy with the same source should leave the function code unchanged. The `.lambda-build/**` exclude alone did not: Deploy Backend `45142626795` ran at 16:56 HKT on #951's commit `2d70da6` and still updated all 21 functions.

## Rollback

Revert the pull request.

## Open questions

None.
