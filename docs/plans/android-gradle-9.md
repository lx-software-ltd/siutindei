# Plan: Gradle 9.5 for the Android app

**Status**: Draft
**Zone**: red

`deploy-mobile.yml` is a red path. This pull request does not run it.

## Goal

Match the Android toolchain `evolvesprouts` already runs: Gradle 9.5.0, Android Gradle plugin 9.3.1, Kotlin 2.4.20, and Temurin 21 for the Gradle process. The app still compiles for Java 17. Pull-request CI builds a debug APK, so the next Flutter or Gradle bump fails before a deploy.

## Non-goals

No iOS change. No signing change. Deploy Mobile and Deploy iOS are not triggered from this pull request.

## Files

`apps/siutindei_app/android/settings.gradle.kts`, `gradle/wrapper/gradle-wrapper.properties`, `app/build.gradle.kts`, `.github/workflows/deploy-mobile.yml`, `.github/workflows/test.yml`, the Android JDK notes, and this plan.

## Invariants this change preserves

`sourceCompatibility`, `targetCompatibility`, and the Kotlin `jvmTarget` stay at 17. The deploy still does not run unless the app paths change on `main`, or someone starts it by hand.

## Done when

`flutter build apk --debug` succeeds on JDK 21, and the `test` gate needs that job.

## Rollback

Revert this pull request.

## Open questions

None.
