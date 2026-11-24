# Plan: Name the dependency workflow Dependency Submission

**Status**: Done
**Zone**: red

## Goal

The Actions tab uses title case, and GitHub's built-in "Dependency Graph"
entry sits next to ours, so this workflow must not use that name. The
workflow display name becomes `Dependency Submission`. The `check` job
display name becomes `Check Dependency Submission`. The `submit` job
display name becomes `Submit Dependency Submission`.

For the same title-case rule, the close-note workflow display name
becomes `Close Auto-Filed NOTE Issues`.

`.github/workflows/dependency-graph.yml` and
`.github/workflows/close-note-tag-issues.yml` sit under `.github/**`.
`docs/architecture/zones.md` names `.github/workflows/deploy-*.yml`,
`promote-*.yml`, `board-*.yml`, and `verify-rulesets.yml` in the red
list. The same page says `.github/**` is refused by the board policy,
because workflow edits ship with the same blast radius as a deploy.
`scripts/ci/board_policy.py` puts `.github` in `PROTECTED_ROOTS`, so
`zone_for_files` labels this diff red. These two files are not in the
yellow paths and not in the green paths. `docs/plans/**` is green
(`docs/**` outside `docs/api/**`). The stricter zone wins.

## Non-goals

File names, job ids, action pins, comments, step names, and every
other line. No Sync Labels workflow. No rename of "Deploy iOS". No
edit to `.pre-commit-config.yaml`. No new tests.

## Files

- `.github/workflows/dependency-graph.yml` — three display names
- `.github/workflows/close-note-tag-issues.yml` — workflow `name:` only
- `docs/plans/2026-11-24-dependency-submission-name.md` — this note

## Invariants this change preserves

Job ids stay `check`, `submit`, and `close-matching`. The job name
"Close matching NOTE-tag issues" stays. Step names stay. The pin
`lx-software-ltd/actions/dependency-graph@7d93bef212616595c866a76b03862eb72abbb746 # main 2026-11-23`
stays, as do the other pins. Triggers, permissions, and `if:`
conditions stay.

## Done when

`python3` on the pinned `workflow-conformance/check_workflows.py`
prints `Workflow conformance passed.` with `CONFORMANCE_MODE=enforce`,
`CONFORMANCE_PROFILE=product`, `CONFORMANCE_ROOT` set to this checkout,
and `CONFORMANCE_ALIGNMENT=warn`. `lint.yml` does not run actionlint.

## Rollback

Revert the commit. No deployed service, schema, or seed data changes.

## Open questions

None.
