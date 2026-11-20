# Plan: Add lint and test merge gates

**Status**: In progress
**Zone**: yellow

Parent plan: Shared actions repository and CI convergence, step SA-101.
The parent is copied to `lx-software-ltd/actions` under `docs/plans/`.

This repository's board policy refuses `.github/**` to board agents. This
change is a normal agent session.

## Goal

`lint.yml` reports a check named `lint` and `test.yml` reports a check named `test`. A pull request runs both workflows with no path filter, so a required check is never skipped. `push` to `main` keeps its path filter.

## Non-goals

- No change to what each existing job checks.
- No change of runner, action pin, or token permissions. Permissions are SA-102.
- No edit to `verify-rulesets.yml` or `board-*.yml`.

## Files

- `.github/workflows/lint.yml`
- `.github/workflows/test.yml`
- `docs/plans/sa-101-lint-test-gates.md`

## Invariants this change preserves

- A pull request to `main` still cannot merge unless checks named `lint` and `test` pass.
- Existing job ids and names stay, so check-run names already reported stay.
- `push` path filters stay.

## Done when

The pull request workflow runs check names `lint` and `test`, and the other check names on `main` are unchanged except for those two additions.

`main` (`87b19155d1ac1dccc20a9b7b98d5497bf7f65bef`) check names:

- Bandit Security Linter
- build-and-deploy
- Check Flutter lockfiles
- Check iOS lockfiles
- Check Node.js lockfiles
- Checkov IaC Security
- Check Python requirements
- CodeQL Analysis
- deploy
- Lint CDK
- Lint Dart
- Lint Python
- Lint React
- PII denylist
- promote
- Python Dependency Audit
- Secret Scanning
- Security Summary
- semgrep/ci
- Test Flutter
- Test Infrastructure
- Test Node
- Test Public Website E2E
- Test Python
- Validate agent harness

## Rollback

Revert the pull request. The path filters and the missing gate jobs return.
