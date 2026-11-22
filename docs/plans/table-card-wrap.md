# Plan: Accept a wrapped catalog action row

**Status**: Draft
**Zone**: yellow

## Goal

The catalog table-card spec allows the release button to wrap onto the next left-aligned row. The actions container is `flex-wrap`. A Node 26 run of `e2e-admin-web.yml` failed because Release was at x 297 and Apply was at x 778. Dispatching that workflow on Node 24 is not available to this token.

## Non-goals

No production layout change. No Node pin change. The Node 24 comparison branch is not merged.

## Files

`apps/admin_web/e2e/table-card.spec.ts` and this plan.

## Invariants this change preserves

Release stays inside the actions container. On one row it is still to the right of Apply. The other table-card assertions stay.

## Done when

The spec no longer requires Release to be to the right of Apply when the row has wrapped.

## Rollback

Revert this pull request.

## Open questions

None.
