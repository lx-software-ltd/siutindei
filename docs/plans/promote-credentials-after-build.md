# Plan: Promote credentials after the build

**Status**: In progress
**Zone**: red

`promote-public-www.yml` is red. This pull request changes only that workflow. No workflow is dispatched.

## Goal

The job that runs `npm ci` and the production build assumes `GitHubActionsRole` only after that build. The live release id, the live commit, and the catalogue snapshot still need the role, and the build needs those files, so a prepare job reads them and uploads the snapshot. The promote job checks out the live commit, builds, then assumes the role, then uploads.

## Non-goals

- No pin change. The shared action stays `b40bb0725bf84f25a38641f6ca5ec6f4c2f14f98`.
- No change to Deploy Public Website. That build still assumes first, because its catalogue snapshot is fetched in the same job.
- No change to the schedule, the modes, or when a refresh is skipped.
- No account id in an `if` expression. No account id in git.
- No promote run.

## Files

`.github/workflows/promote-public-www.yml`, this plan.

## Invariants this change preserves

- A schedule still refreshes production. A matching catalogue digest still skips the build.
- A missing production marker still skips. Maintenance still skips the build and still promotes.
- The snapshot schema check stays in the fetch script. A refresh still checks out the recorded commit before `npm ci`.
- The account id is `secrets.AWS_ACCOUNT_ID` only.

## Done when

In the promote job, the credentials step is after "Build public website for production". Workflow conformance in enforce mode still reports one actions commit.

## Rollback

Revert this pull request.

## Open questions

None.
