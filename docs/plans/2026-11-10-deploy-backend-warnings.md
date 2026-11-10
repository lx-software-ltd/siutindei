# Plan: Clear Deploy Backend template warnings

**Status**: Implemented
**Zone**: red (`backend/infrastructure/**`, `.github/workflows/deploy-backend.yml`, `.github/workflows/cdk-diff.yml`)

## Goal

Clear the warnings from Deploy Backend run 42747392146.

- Call `addResourceDependency` on the Cognito user-pool clients.
- Acknowledge `CloudFormation-Validate::F3002` on the RDS proxy target group. CDK emits `Tags` and the deployed group already has them. Removing the property would update the live group.
- Default `OpenRouterApiKey` to `pending`, the same placeholder an empty value already stores, so SecretString is never an empty string.
- Acknowledge `CloudFormation-Validate::W3011` on the Lambda and migration security groups. Replacement still retains the named group, and stack deletion still removes it.
- Stop passing the bootstrap-only qualifier flag to the deploy, destroy, and diff commands. The app already reads `CDK_BOOTSTRAP_QUALIFIER`.

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
- `.github/workflows/cdk-diff.yml`
- `docs/architecture/aws-assets-map.md`
- `docs/architecture/security.md`

## Invariants this change preserves

- The user pool client still depends on the Google and Apple identity providers.
- An empty OpenRouter parameter still stores the secret value `pending`. A provided key is still stored as itself.
- `LambdaSecurityGroup` and `MigrationSecurityGroup` still have `UpdateReplacePolicy: Retain` and no `DeletionPolicy`.
- Bootstrap still receives the qualifier flag when `CDK_BOOTSTRAP_QUALIFIER` is set.
- The proxy target group template still includes its tags.
- No schema, seed, or API change.

## Done when

- `npm run build` and `npm run test:infra` pass in `backend/infrastructure`.
- `test:infra` sets `JSII_DEPRECATED=fail`, so a deprecated call throws.
- The API stack synthesis report has no unsuppressed validation violations.

## Rollback

Revert the commits on this branch. The previous parameter default is an empty string, and the deploy and diff commands pass the ignored qualifier flag.

## Open questions

None.
