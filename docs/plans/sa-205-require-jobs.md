# Plan: Call require-jobs from the lint and test gates

**Status**: In progress
**Zone**: yellow

Parent plan: Shared actions repository and CI convergence, `lx-software-ltd/actions` `docs/plans/shared-actions-and-ci-convergence.md`, step SA-205.

This repository's board policy refuses `.github/**` to board agents. This change is a normal agent session. `lint.yml` and `test.yml` are not on the red list in `docs/architecture/zones.md`.

`findingalpha` #72 merged first, at `d924cc4b1bdee7477b49b3352eccd7a4762639ea`. This pull request, #920, merges after that.

## Goal

The gate step in job `lint` and the gate step in job `test` call `lx-software-ltd/actions/require-jobs` at `1a3cca7c38163f8164c262323601c34a4df5b7a4` (`main`, 2026-11-20) and pass `needs-json: ${{ toJson(needs) }}`. The action fails unless every needed job succeeded. Skipped stays a failure, which is the action default.

## Non-goals

- No change to other steps, action pins, runners, permissions, path filters, or `if: always()`.
- No `setup-python` on the gate. The action runs `python3` on the runner.
- No edit to board workflows, deploy, promote, PII scripts, pre-commit, or architecture docs.
- No test edit. No test asserts the old inline gate text.

## Files

- `.github/workflows/lint.yml` (job `lint` only)
- `.github/workflows/test.yml` (job `test` only)
- `docs/plans/sa-205-require-jobs.md`

## Invariants this change preserves

- Job ids stay `lint` and `test`. Job names stay `lint` and `test`. Both stay `runs-on: ubuntu-latest` with `if: always()`.
- `needs` lists stay: lint needs `validate-agent-harness`, `lint-dart`, `lint-react`, `lint-python`, and `lint-cdk`. Test needs `pii-denylist`, `test-flutter`, `test-node`, `test-public-www-e2e`, `test-python`, and `test-infrastructure`.
- Step names stay `Require every lint job` and `Require every test job`.
- A pull request to `main` still cannot merge unless checks named `lint` and `test` pass.

## Check names on main

Rollout step 2. `main` `754ee28cd91ffbce371f001139be5d317cddbebd` github-actions check names, all success. `PII denylist` is two jobs that share that name:

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

## Check names on the pull request head

Rollout step 4. Head `7d2f69069b9b7c967009ea3d7bb4035ff8b11016`. The github-actions names are the same list, including both `PII denylist` jobs, `semgrep/ci`, `lint`, and `test`. Both gates succeeded. Checkov, CodeQL, and Semgrep OSS are `github-advanced-security` uploads on the pull request. They are code-scanning results, not renamed jobs.

## Done when

Both gate steps use the pinned action and pass `needs-json`. The rest of each workflow file is unchanged. The two check-name lists above are the rollout evidence. This pull request merges after `findingalpha` #72, which has merged.

## Rollback

Revert this pull request. The inline Python gate steps return, and `main` protection keeps the previous commit reachable. Board, deploy, promote, and PII files are not in the change, so they stay as they are.

## Open questions

None.
