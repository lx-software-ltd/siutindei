# Plan: Call verify-rulesets from the weekly ruleset job

**Status**: In progress
**Zone**: yellow

Parent plan: Shared actions repository and CI convergence, `lx-software-ltd/actions` `docs/plans/shared-actions-and-ci-convergence.md`, step SA-304.

This repository's board policy refuses `.github/**` to board agents. This change is a normal agent session. Gate G1 is approved. The expected approving-review count is exactly 0, and the required checks are exactly `lint` and `test`.

A pull request is opened for this change.

## Goal

The Monday 23 Nov 2026 09:00 UTC run of **Verify GitHub Rulesets** must stop failing with `main ruleset does not require at least 1 approving review.` Gate G1 replaces `scripts/verify_github_rulesets.py` with `lx-software-ltd/actions/verify-rulesets` at `61d2a581a1d880533982bada88923ad1b6431700` (`main`, 2026-11-20). The step passes `expected-reviews: "0"` and `required-checks: lint test`. The action expects exactly 0 approving reviews. It does not keep the local script's "at least 1" error.

`docs/architecture/github-rulesets.md` is corrected to that live contract. Required approvals are exactly 0. Required contexts are exactly `lint` and `test`. The doc says the weekly job fails if the count is not 0 or the check list is not exactly those two names. It no longer says the job is waiting on an admin to activate a disabled ruleset, and it no longer names the deleted script.

## Non-goals

- No edit to deploy, Amplify, board, lint, test, or security workflows.
- No runner change. No job id change. No workflow name change.
- No `workflow_dispatch` of this job from this change, and no merge.
- Staging protection, tag protection, and unrelated prose in `docs/architecture/github-rulesets.md` stay as they are.

## Files

- `.github/workflows/verify-rulesets.yml`
- `scripts/verify_github_rulesets.py` (deleted)
- `tests/test_agent_harness_checks.py` (the two tests that load the deleted script)
- `docs/architecture/github-rulesets.md` (live contract: exactly 0 approving reviews, required checks exactly `lint` and `test`)
- `docs/plans/sa-304-verify-rulesets.md`

## Invariants this change preserves

- Workflow name stays `Verify GitHub Rulesets`.
- Cron stays `"0 9 * * 1"`. `workflow_dispatch` stays.
- Permissions stay `contents: read`.
- Job id stays `verify-branch-protection`. The job has no name.
- `runs-on` stays `ubuntu-latest`.
- Checkout stays `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` `# v7.0.1`.
- The Summary step still points at `docs/architecture/github-rulesets.md`.
- No `${{ }}` expression sits inside a `run` script.

## Check names on main

`main` `fe2c76663d4d26a5fb4409ca73ad4bf3ba543e58` github-actions check names, all success. `PII denylist` is two jobs that share that name. Gate G1 requires the checks named `lint` and `test`, and both are success on that commit:

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

The verify step uses the pin above and passes `expected-reviews: "0"` and `required-checks: lint test`. `scripts/verify_github_rulesets.py` is gone, and the harness tests that loaded it are gone. The Monday failure string is not produced by a local script. `docs/architecture/github-rulesets.md` states exactly 0 approving reviews and required checks `lint` and `test`. A pull request is opened. This pull request is not merged.

## Rollback

Revert the pull request. The weekly job returns to `scripts/verify_github_rulesets.py`, and `main` protection keeps the previous commit reachable.

## Open questions

None.
