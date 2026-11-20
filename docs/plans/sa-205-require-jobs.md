# Plan: Call require-jobs from the lint and test gates

**Status**: In progress
**Zone**: yellow

Parent plan: Shared actions repository and CI convergence, step SA-205.
The parent is copied to `lx-software-ltd/actions` under `docs/plans/`.

This repository's board policy refuses `.github/**` to board agents. This
change is a normal agent session. `lint.yml` and `test.yml` are not on
the red list in `docs/architecture/zones.md`.

## Goal

The gate step in job `lint` and the gate step in job `test` call
`lx-software-ltd/actions/require-jobs` at
`1a3cca7c38163f8164c262323601c34a4df5b7a4` (`main`, 2026-11-20) and pass
`needs-json: ${{ toJson(needs) }}`. The action fails unless every needed
job succeeded. Skipped stays a failure, which is the action default.

## Non-goals

- No change to other steps, action pins, runners, permissions, path
  filters, or `if: always()`.
- No `setup-python` on the gate. The action runs `python3` on the runner.
- No edit to board workflows, deploy, promote, PII scripts, pre-commit,
  or architecture docs.
- No workflow dispatch and no pull request from this change.
- No test edit. No test asserts the old inline gate text.

## Files

- `.github/workflows/lint.yml` (job `lint` only)
- `.github/workflows/test.yml` (job `test` only)
- `docs/plans/sa-205-require-jobs.md`

## Invariants this change preserves

- Job ids stay `lint` and `test`. Job names stay `lint` and `test`.
  Both stay `runs-on: ubuntu-latest` with `if: always()`.
- `needs` lists stay: lint needs `validate-agent-harness`, `lint-dart`,
  `lint-react`, `lint-python`, and `lint-cdk`. Test needs
  `pii-denylist`, `test-flutter`, `test-node`, `test-public-www-e2e`,
  `test-python`, and `test-infrastructure`.
- Step names stay `Require every lint job` and `Require every test job`.
- A pull request to `main` still cannot merge unless checks named
  `lint` and `test` pass.

## Done when

Both gate steps use the pinned action and pass `needs-json`. The rest
of each workflow file is unchanged.

`main` tip `754ee28cd91ffbce371f001139be5d317cddbebd` check names:

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

This branch does not open a pull request. Those checks do not run on
the branch until one exists.

## Rollback

Revert the commit. The inline Python gates return.

## Open questions

None.
