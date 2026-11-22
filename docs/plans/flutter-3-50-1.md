# Plan: Pin Flutter 3.50.1

**Status**: Draft
**Zone**: red

`deploy-ios.yml` and `deploy-mobile.yml` are red. This pull request does not run them.

## Goal

Every passed `flutter-version` is `3.50.1`, the same pin `evolvesprouts` already uses.

## Non-goals

`pubspec.lock` is unchanged. The CI SDK pin does not rewrite the package lock. The owner runs the mobile deploys after merge (O7).

## Files

`.github/workflows/check-lockfiles.yml`, `lint.yml`, `test.yml`, `deploy-mobile.yml`, `deploy-ios.yml`, this plan.

## Invariants this change preserves

The subosito action pin stays. Lockfiles are not regenerated.

## Done when

No workflow passes `3.47.9`.

## Rollback

Revert this pull request.

## Open questions

None.
