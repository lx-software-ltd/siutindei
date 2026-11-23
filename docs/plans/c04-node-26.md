# Plan: Node 26 and the actions pin

**Status**: Draft
**Zone**: red

The pre-commit `rev` is a red path. Pair B also pins `verify-rulesets.yml`, which is red. Deploy workflows that still pass an older Node version are red. Gate G2 already covers the hook repository. This pull request does not change hook behaviour: `9235676` does not touch the hook scripts or `verify-rulesets`.

This pull request does not run a deploy, bootstrap, or key-management workflow. For the workflows that move from Node 24 to Node 26, that means the first real run is later, not at merge. The section below names those workflows.

## Goal

Move every `lx-software-ltd/actions` pin and the pre-commit `rev` from `61b67ed4f686659433f6ca4cb10c80707e365cd0` to `9235676200771b2f93bc01ac85f3de1392133182`. Finish C04: the shared `setup-node` action is called without `node-version`, so its default `26` applies. A direct `actions/setup-node` call that is not already `26` passes `"26"`.

## Non-goals

Stages 5 and 6. SA-701 and SA-702. Flutter version pins. No deploy, bootstrap, or key-management workflow is triggered.

## Files

`.github/workflows/*.yml`, `.pre-commit-config.yaml`, this plan.
`board-merge-staging.yml` drops the quotes around `statuses`. It does not set a Node version.

## When Node 26 first runs

`lts/*` already selects Node 26, so `cdk-diff.yml` and `deploy-backend.yml` do not change the runtime when their string becomes `"26"`.

These workflows move from Node 24 to Node 26. That is a major-version jump:

- `deploy-admin-web.yml`
- `deploy-public-www.yml`
- `promote-public-www.yml`
- `smoke-public-www-staging.yml`
- `cdk-bootstrap.yml`
- `lighthouse-public-www.yml`
- `e2e-admin-web.yml`

Pull-request CI builds and tests the public site on Node 26. Those checks passed on this pull request.

`e2e-admin-web.yml` runs only when someone starts it. This pull request did not start it, so the admin-web end-to-end suite has not run on Node 26.

`deploy-admin-web.yml` runs on a manual start, or on a push to `main` that touches `apps/admin_web/**`, `packages/react_ui/**`, `packages/api_client_ts/**`, `packages/models_shared/**`, or `scripts/**`. This pull request does not touch those paths, so the merge does not start that deploy. The first Node 26 admin deploy will be some later push that does. A failure on that later push will not point back at this pull request.

`deploy-public-www.yml` runs for `staging`, a manual start, or `repository_dispatch`. `promote-public-www.yml` runs on its schedule, a manual start, or `repository_dispatch`. `smoke-public-www-staging.yml`, `lighthouse-public-www.yml`, and `cdk-bootstrap.yml` run when someone starts them. None of those starts is this merge.

## Invariants this change preserves

- One actions commit. `workflow-conformance` stays `mode: enforce`.
- `lint` and `test` stay the required check names.
- Direct `actions/setup-node` calls that already pass `"26"` stay as they are. That action has no organisation default.
- No long-lived AWS key is added.

## Done when

No workflow passes `node-version: lts/*`, `24`, or `22.22.2`. Every shared `setup-node` call omits `node-version`. The actions pin and the pre-commit `rev` are `9235676200771b2f93bc01ac85f3de1392133182`.

## Rollback

Revert this pull request. The previous pin stays valid.

## Open questions

None.
