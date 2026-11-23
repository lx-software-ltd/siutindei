# Plan: OpenAPI lint error ceiling

**Status**: Draft
**Zone**: yellow

## Goal

`lint` fails when `@redocly/cli@1.34.11` reports more than 176 errors in `docs/api/admin.yaml`, `docs/api/partner.yaml`, and `docs/api/search.yaml`. The 176 existing errors stay allowed. The 299 warnings are printed and are not part of the ceiling.

## Non-goals

An ignore file. Fixing the existing errors. Changing `scripts/check_openapi_routes.py`. mypy, which stays on pre-commit. A coverage change.

## Files

`.github/workflows/lint.yml` and this plan.

## Invariants this change preserves

The `lint` job id and its display name stay `lint`. The actions pin stays `ffde04dca3c78b1ccb8739f4d3a23f728ac7a05f`. A Redocly exit code above 1, or a run that prints no error count, still fails the job.

## Done when

The `lint` job needs `lint-openapi`, and that job prints `OpenAPI errors: 176 (ceiling 176)`.

## Rollback

Revert this pull request.

## Open questions

None.
