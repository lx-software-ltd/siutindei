# Plan: Call setup-node and setup-python from CI

**Status**: In progress
**Zone**: yellow

Parent plan: [Shared actions repository and CI convergence](https://github.com/lx-software-ltd/actions/blob/61d2a581a1d880533982bada88923ad1b6431700/docs/plans/shared-actions-and-ci-convergence.md), step SA-301.

This repository's board policy refuses `.github/**` to board agents. This change is a normal agent session. `lint.yml`, `test.yml`, `security.yml`, and `check-lockfiles.yml` are not on the red list in `docs/architecture/zones.md`.

A pull request is opened.

**Intent**: Replace `actions/setup-node` and `actions/setup-python` in the pull-request CI workflows with the shared composites, and pass each job's current Node and Python version.

## Goal

Call `lx-software-ltd/actions` `setup-node` and `setup-python` from the pull-request CI workflows, pinned at `61d2a581a1d880533982bada88923ad1b6431700` with the comment `# main 2026-11-20`. Each caller passes the Node or Python version it uses today, so the action defaults Node 26 and Python 3.12 do not apply by omission. Move `require-jobs` in `lint.yml` and `test.yml` from `1a3cca7c38163f8164c262323601c34a4df5b7a4` to that same commit.

## Non-goals

- No Node 26 switch and no Python 3.12 switch for a job that is not already on that version.
- No edit to deploy workflows, promote workflows, Amplify workflows, key workflows, or board workflows. This repository has no key-management workflow.
- No edit to `cdk-diff.yml`, `cdk-bootstrap.yml`, `e2e-admin-web.yml`, `lighthouse-public-www.yml`, or `smoke-public-www-staging.yml`. Those stay on `actions/setup-node` and `actions/setup-python`.
- No `runs-on` change. Checkout refs stay. No `v*` tag. No other action pin.
- No edit to PII scripts or the denylist.

## Pin

`61d2a581a1d880533982bada88923ad1b6431700` `# main 2026-11-20`

The pin is `61d2a58` so this pull request and the ruleset pull request use one actions SHA.

Every `lx-software-ltd/actions` reference in the workflows this change touches uses that SHA, including `require-jobs`.

## Files

- `.github/workflows/lint.yml`
- `.github/workflows/test.yml`
- `.github/workflows/security.yml`
- `.github/workflows/check-lockfiles.yml`
- `docs/plans/sa-301-setup-actions.md`

`npm ci` is folded into `setup-node` where that install step is exactly `npm ci` in the lockfile directory (`cache: npm`, `working-directory`, and the `npm ci` step deleted):

- `backend/infrastructure` in Lint CDK and Checkov IaC Security
- `apps/public_www` in Test Public Website E2E (the job `defaults.run.working-directory`)

These install steps stay, and those setup calls pass `node-version` only:

- Lint React, Test Node, and Check Node.js lockfiles, each a loop that runs `npm ci` or `npm install`
- Test Infrastructure, a conditional script that `cd`s and runs `npm ci`

Validate agent harness does not run `npm ci`. It passes `node-version` only and does not set `cache: npm`.

Lint Python is the only caller that caches pip today (`cache: pip`, default dependency path `**/requirements.txt`, which is `backend/requirements.txt`). It passes `python-version` and `requirements: backend/requirements.txt`. Every other Python caller passes only `python-version`.

## Workflows left

Deploy and promote, still on `actions/setup-node` or `actions/setup-python`:

- `.github/workflows/deploy-admin-web.yml`
- `.github/workflows/deploy-backend.yml`
- `.github/workflows/deploy-ios.yml`
- `.github/workflows/deploy-mobile.yml`
- `.github/workflows/deploy-public-www.yml`
- `.github/workflows/promote-public-www.yml`

Amplify: `.github/workflows/amplify-promote.yml` (no setup-node or setup-python step).

Board, still on the previous setup action where one exists:

- `.github/workflows/board-agent.yml`
- `.github/workflows/board-merge-staging.yml`
- `.github/workflows/board-promote.yml`

Also left, with their current setup actions:

- `.github/workflows/cdk-diff.yml` (Node `lts/*`, Python 3.12)
- `.github/workflows/cdk-bootstrap.yml` (Node 24, Python 3.12)
- `.github/workflows/e2e-admin-web.yml` (Node 24)
- `.github/workflows/lighthouse-public-www.yml` (Node 24)
- `.github/workflows/smoke-public-www-staging.yml` (Node 24)
- `.github/workflows/semgrep.yml`
- `.github/workflows/verify-rulesets.yml`
- `.github/workflows/close-note-tag-issues.yml`

## Invariants this change preserves

- Node 24 stays 24 on every edited job that uses 24: Validate agent harness, Lint React, Lint Python, Lint CDK, Test Node, Test Public Website E2E, Test Infrastructure, Checkov IaC Security, and Check Node.js lockfiles.
- Python 3.13 stays 3.13 on Lint Python, Python Dependency Audit, and Bandit Security Linter.
- Python 3.12 stays 3.12 on Validate agent harness, Lint CDK, PII denylist in `test.yml`, Test Python, Checkov IaC Security, and PII denylist in `security.yml`.
- `runs-on` stays `ubuntu-latest` on those jobs, and Check iOS lockfiles stays `macos-latest`.
- Checkout stays `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`.
- Gate jobs keep `needs`, `if: always()`, the step name, and `needs-json`. No setup step in these files had an `if:`.
- Job names stay. No secret is added.

## Check names on main

`main` `fe2c76663d4d26a5fb4409ca73ad4bf3ba543e58`, github-actions check names, all success. Two jobs share the name `PII denylist`:

- Bandit Security Linter
- Check Flutter lockfiles
- Check iOS lockfiles
- Check Node.js lockfiles
- Check Python requirements
- Checkov IaC Security
- CodeQL Analysis
- Lint CDK
- Lint Dart
- Lint Python
- Lint React
- PII denylist
- PII denylist
- Python Dependency Audit
- Secret Scanning
- Security Summary
- Test Flutter
- Test Infrastructure
- Test Node
- Test Public Website E2E
- Test Python
- Validate agent harness
- lint
- semgrep/ci
- test

## Done when

The four workflow files contain no `uses: actions/setup-node@` and no `uses: actions/setup-python@`, and no `1a3cca7`. Every `lx-software-ltd/actions` reference in those files is `61d2a581a1d880533982bada88923ad1b6431700`. Node 24 and Python 3.13 are still passed explicitly. Runners are unchanged. Deploy, promote, Amplify, and board workflows are unchanged.

No test asserts the old setup action text, so no test file changes.

## Rollback

Revert the pull request. The `actions/setup-node` and `actions/setup-python` steps return, and `require-jobs` returns to `1a3cca7c38163f8164c262323601c34a4df5b7a4`. Deploy, promote, Amplify, board, and the other workflows listed above are not in the change, so they stay as they are.

## Open questions

None.
