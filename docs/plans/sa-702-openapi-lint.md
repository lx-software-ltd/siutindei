# Plan: OpenAPI lint

**Status**: Draft
**Zone**: yellow

## Goal

`lint` runs `@redocly/cli@1.34.11` on `docs/api/admin.yaml`, `docs/api/partner.yaml`, and `docs/api/search.yaml`, and the job fails when that command fails.

## What was wrong

The three specs had 176 errors: 151 admin operations with no `security`, 22 `nullable` fields with no `type`, and no `servers` entry. Those are fixed in the specs. The lint does not ignore them.

## Non-goals

An ignore file. An error ceiling. mypy, which stays on pre-commit. A coverage change. The 299 Redocly warnings (`operationId`, `4xx` responses, license, ambiguous paths, unused components) still print. They do not fail this command.

## Files

`docs/api/admin.yaml`, `docs/api/partner.yaml`, `docs/api/search.yaml`, `.github/workflows/lint.yml`, and this plan.

## Invariants this change preserves

The `lint` job id and its display name stay `lint`. The actions pin stays `ffde04dca3c78b1ccb8739f4d3a23f728ac7a05f`. `scripts/check_openapi_routes.py` still passes. Security on each operation matches the authorizer that API Gateway already uses: admin, manager, any signed-in user, importer on the import and organization routes the authorizer allows, and IAM on `/health`.

## Done when

`npx --yes @redocly/cli@1.34.11 lint` on the three specs exits 0, and the `lint` job needs `lint-openapi`.

## Rollback

Revert this pull request.

## Open questions

None.
