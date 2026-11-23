# Android signing setup

This directory contains signing configuration templates for CI and local
builds.

## Local setup

1. Copy `key.properties.example` to `key.properties`.
2. Place your `keystore.p12` in this directory.
3. `android/app/build.gradle.kts` already applies `signing.gradle`
   (`apply(from = "signing.gradle")`). `storeFile` resolves relative to
   this directory. Without a readable keystore the release build falls
   back to debug signing.
4. Use JDK 21 (`flutter config --jdk-dir <jdk21>`). Android Gradle Plugin
   9.3 runs on Java 21. The app still compiles for Java 17.

Do not commit `key.properties` or `keystore.p12`.

## CI setup

Provide environment variables in CI:

- `KEYSTORE_PATH` (recommended: `app/keystore.p12`)
- `KEYSTORE_PASSWORD`
- `KEY_ALIAS`
- `KEY_PASSWORD`

Then decode the keystore to `apps/siutindei_app/android/app/keystore.p12`.
