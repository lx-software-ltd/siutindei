# Plan: SA-503 shared AWS actions

**Status**: In progress
**Zone**: red

`.pre-commit-config.yaml` is red. This pull request changes only its `rev`, because workflow conformance allows one `lx-software-ltd/actions` commit and that rev has to be the same commit. The workflows that assume `GitHubActionsRole` are red. No workflow is dispatched.

## Goal

Pin every shared action and the pre-commit rev to `b40bb0725bf84f25a38641f6ca5ec6f4c2f14f98`, the same commit as lx-software #675, with `# main 2026-11-23`. Call `aws-oidc` wherever the workflow assumed `GitHubActionsRole`. `cdk-diff.yml` calls `cdk-bootstrap-check` and `cdk-diff`. The account id is `secrets.AWS_ACCOUNT_ID` only. CDK Diff stays `repository_dispatch` and `workflow_dispatch`. Menu labels still map to the same stack names, including `us-east-1` for the WAF label. An empty input still diffs the three app stacks, not the WAF stack.

## Non-goals

- No `cfn-stack-outputs` call. No workflow reads a required fixed set of stack outputs. Promote and backend reads stay inline.
- No removal of `cdk bootstrap` from Deploy Backend. That command is C24.
- The public-website credentials stay before the build. The catalogue snapshot needs the role, and the build needs the snapshot.
- No new `pull_request` trigger. No second actions commit.
- No account id in git. No deploy, bootstrap, or promote run.

## Files

The workflows that assumed the role, the other workflow pins, `.pre-commit-config.yaml`, this plan.

## Invariants this change preserves

- Admin web still builds before the role, then starts Amplify only when the app id and branch are set.
- Deploy Backend still runs `cdk bootstrap` before deploy.
- The WAF diff still assumes the role in `us-east-1`.
- The account id is not placed in an `if` expression.

## Done when

Workflow conformance in enforce mode reports one actions commit. No workflow calls `configure-aws-credentials`.

## Rollback

Revert this pull request. The previous pin is `9235676200771b2f93bc01ac85f3de1392133182`.

## Open questions

None.
