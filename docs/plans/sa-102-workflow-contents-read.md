# Plan: Read-only workflow tokens

**Status**: In progress
**Zone**: yellow

Parent plan: Shared actions repository and CI convergence, step SA-102.
Normal agent session. Board workflows are not touched.

## Goal

lint.yml, test.yml, check-lockfiles.yml, and e2e-admin-web.yml set permissions contents read at the top. No job in these files asks the token for more.

## Non-goals

No job logic change. No runner change. verify-rulesets.yml already sets contents read. board workflows are out of scope.

## Files

- .github/workflows/lint.yml
- .github/workflows/test.yml
- .github/workflows/check-lockfiles.yml
- .github/workflows/e2e-admin-web.yml
- docs/plans/sa-102-workflow-contents-read.md

## Invariants this change preserves

Checkout still works. The gate jobs lint and test stay. No secret is added.

## Done when

Each of the four workflows has a top-level permissions block of contents read, and no job overrides it.

## Rollback

Revert the pull request.
