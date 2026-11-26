# Plan: one API standard

**Status**: In progress
**Zone**: red

## Goal

Give siutindei the shared API shape. The production hostname stays on the
domain construct that already exists. Later pull requests move the server
routes, the website, and then remove the old edge paths.

The written standard is `docs/plans/api-standard.md` in
`lx-software-ltd/actions` at
`dadcbf4d63519cb93117f85925b6f90e013e057b`.

## Non-goals

Scope names, token expiry, generated clients, and a staging API.

## Files

- `backend/infrastructure/lib/api-stack.ts`
- `backend/infrastructure/params/production.json`
- `backend/infrastructure/scripts/assert-existing-db.ts`
- `scripts/deploy/build_amplify_config.py`
- `.github/workflows/deploy-backend.yml`
- `.github/workflows/cdk-diff.yml`
- The docs named in the actions plan

## Invariants this change preserves

- The construct ids `ApiSecondaryCustomDomain`, `ApiSecondaryCertificate`,
  and `ApiSecondaryBasePathMapping` do not change.
- The certificate secret name stays
  `CDK_PARAM_API_SECONDARY_CUSTOM_DOMAIN_CERTIFICATE_ARN`.
- `backend/db/**` is not edited.

## Done when

The last pull request in this series deletes this note. Each pull request
records the commands from the actions plan.

## Rollback

Revert the pull request.

## Open questions

None.
