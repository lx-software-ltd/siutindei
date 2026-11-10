# Plan: Clear Deploy Backend template warnings

**Status**: Implemented
**Zone**: red (`backend/infrastructure/**`, `.github/workflows/deploy-backend.yml`)

## Goal

Clear the warnings from Deploy Backend run 42747392146.

- Call `addResourceDependency` on the Cognito user-pool clients.
- Drop `Tags` from the RDS proxy target group. The resource schema rejects them. The proxy and the cluster keep the stack tags.
- Default `OpenRouterApiKey` to `pending`, the same placeholder an empty value already stores, so SecretString is never an empty string.
- Acknowledge `CloudFormation-Validate::W3011` on the Lambda and migration security groups. Replacement still retains the named group, and stack deletion still removes it.
- Stop passing `--qualifier` to `cdk deploy` and `cdk destroy`. The flag is bootstrap-only and the app already reads `CDK_BOOTSTRAP_QUALIFIER`.

## Non-goals

- Pinning `ubuntu-latest`.
- Splitting the API stack. The 495-resource notice is below the 500 limit.
- Changing log-bucket `AccessControl`. CDK already acknowledges that deprecation.
- Setting `DeletionPolicy: Retain` on the named security groups.

## Files

- `backend/infrastructure/lib/api-stack.ts`
- `backend/infrastructure/lib/constructs/auth.ts`
- `backend/infrastructure/lib/constructs/database.ts`
- `backend/infrastructure/scripts/assert-existing-db.ts`
- `.github/workflows/deploy-backend.yml`
- `docs/architecture/aws-assets-map.md`
- `docs/architecture/security.md`

## Invariants this change preserves

- The user pool client still depends on the Google and Apple identity providers.
- An empty OpenRouter parameter still stores the secret value `pending`. A provided key is still stored as itself.
- `LambdaSecurityGroup` and `MigrationSecurityGroup` still have `UpdateReplacePolicy: Retain` and no `DeletionPolicy`.
- Bootstrap still receives `--qualifier` when `CDK_BOOTSTRAP_QUALIFIER` is set.
- No schema, seed, or API change.

## Done when

- `npm run build` and `npm run test:infra` pass in `backend/infrastructure`.
- The API stack synthesis report has no unsuppressed validation violations, and stderr does not mention `CfnResource#addDependency`.

## Rollback

Revert the commits on this branch. The previous parameter default is an empty string, the target group carries stack tags, and deploy passes the ignored `--qualifier` flag.

## Open questions

None.
