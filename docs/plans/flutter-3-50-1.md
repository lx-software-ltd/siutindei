# Plan: Pin Flutter 3.50.1

**Status**: Draft
**Zone**: red

`deploy-ios.yml` and `deploy-mobile.yml` are red. This pull request does not run them.

## Goal

Every passed `flutter-version` is `3.50.1`, the same pin `evolvesprouts` already uses.

## Lockfile

`flutter pub get` on 3.50.1 moves transitive `test_api` from 0.7.12 to 0.7.14. That is the same resolution `evolvesprouts` already has. The app also depends on `material_ui` 1.11.0, which was already in the lock as a transitive package. Flutter 3.50.1 deprecates `package:flutter/material.dart` in favour of that package, and `flutter analyze` fails on the deprecation. The imports now use `package:material_ui/material_ui.dart`, the same import `evolvesprouts` uses. No other package version moves.

## Non-goals

The owner runs the mobile deploys after merge (O7).

## Files

`.github/workflows/check-lockfiles.yml`, `lint.yml`, `test.yml`, `deploy-mobile.yml`, `deploy-ios.yml`, `apps/siutindei_app/pubspec.yaml`, `apps/siutindei_app/pubspec.lock`, the Dart imports that used `package:flutter/material.dart`, and this plan.

## Invariants this change preserves

The subosito action pin stays. Lockfiles are not regenerated.

## Done when

No workflow passes `3.47.9`.

## Rollback

Revert this pull request.

## Open questions

None.
