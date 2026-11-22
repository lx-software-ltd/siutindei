# Plan: Wave 3 close-out

**Status**: Draft
**Zone**: red

## Goal

Move `siutindei` onto the shared actions commit and close the CI convergence rows that apply to this Amplify and Flutter repository. The closing commit sets `workflow-conformance` to enforce.

## Non-goals

No merge, no pull request, and no workflow run. Dependabot `cooldown.exclude` is not added. Board workflow behavior stays the same apart from the runner label, the Postgres image digest, the Node and Python versions, and the quoted `statuses` permission. Expressions that read `AWS_ACCOUNT_ID`, secrets, or vars are unchanged. Deploy, bootstrap, and key-management workflows are not triggered.

## Files

`.github/workflows/`, `.pre-commit-config.yaml`, `.cursor/hooks/stop_gate.py`, `.cursor/rules/00-repository-core.mdc`, `.cursor/skills/verify-change/SKILL.md`, `.cursor/skills/cursor-cloud/SKILL.md`, `docs/architecture/zones.md`, `scripts/ci/board_policy.py`, `tests/test_agent_harness_checks.py`, and the deleted local hook scripts.

## Invariants this change preserves

- One `lx-software-ltd/actions` commit: `61b67ed4f686659433f6ca4cb10c80707e365cd0`.
- The pre-commit `rev` is that same commit.
- `lint` and `test` stay the required check names. Pair B has no `changes` job and no `allow-skipped` input, and neither was added.
- The PII denylist file stays. The hook reads it. No plaintext was added.
- Semgrep uploads with category `semgrep`. CodeQL Python stays `/language:python`. `javascript-typescript` is a new category, `/language:javascript-typescript`.
- Flutter stays `3.47.9` wherever it was already set. Every `subosito/flutter-action` step already passed that version.
- Dependabot already set `cooldown.default-days` to 7 on every ecosystem. No exclude was added.
- Board account-id expressions are unchanged.

## Done when

- `workflow-conformance` in enforce mode reports no findings.
- Runners are `ubuntu-26.04` and `macos-26`. Jobs a pull request runs use Node `"26"`. Workflows a pull request does not run keep the previous `node-version` string: deploy, promote, bootstrap, diff, e2e, Lighthouse, and the staging smoke workflow. Those strings are `"24"`, `'24'`, or `"lts/*"`, copied from `main`. Python `3.13` is now `"3.12"`.
- Semgrep runs `mode: scan`, which reads the whole repository. This file was already scan, not `semgrep ci`. The packs are `p/python`, `p/javascript`, `p/security-audit`, `p/secrets`, and `p/owasp-top-ten`. The added pack is `p/javascript`. The urllib rule is not excluded. `cfn_response.py` marks its reviewed `urlopen` with `nosemgrep`. `aws_proxy.py` is checked. `gha-curl-pipe-shell` stays excluded because it warns on `${{ }}` in `run:` blocks. `upload: "false"` keeps the existing upload step on category `semgrep`. The Dependabot skip stays.
- Bandit on `backend/src` and `backend/lambda` exits 0 with no skip. Measured 22 Nov 2026: no high findings. Two `B310` `urlopen` calls are `# nosec B310` on the line, in `cfn_response.py` and `aws_proxy.py`, and both validate the URL before use. `B105` and `B106` do not match.
- `npm audit --omit=dev --audit-level=high` reports no high advisory in `apps/admin_web`, `apps/public_www`, and `backend/infrastructure`. `packages/react_ui` and `packages/api_client_ts` have no `package.json`, and the lockfile job still skips them.
- `pip-audit` on `backend/requirements.txt`, ignoring `PYSEC-2025-183`, reports no known vulnerabilities. Python requirement pins pass.
- The agent harness check passes after the core-rule denylist sentence change. The `[why:]` tag is unchanged.
- `python3 -m pytest tests/test_agent_harness_checks.py tests/test_board_policy.py` passes. A machine without `pre-commit` on `PATH` gets one follow-up from the stop hook. The first `pre-commit` run needs network to clone `lx-software-ltd/actions`. A real non-zero hook failure does not add that sentence.

## Rollback

Revert this branch. The previous actions pin is `aab84b76383d5a44838f9617ac47b23cfff7fdaf`.

## Open questions

None. The Semgrep category stayed `semgrep`, and the new CodeQL language did not rename the Python category, so the existing alerts stay attached.
