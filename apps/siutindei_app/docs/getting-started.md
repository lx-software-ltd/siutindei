# Getting Started

This guide will help you set up and run the Siutindei App locally.

## Prerequisites

### Required Tools

- **Flutter SDK** 3.41 or later (stable)
- **Dart SDK** 3.10.3 or later (included with Flutter)
- **Git** for version control

### Platform-Specific

#### iOS Development
- macOS with Xcode 14 or later
- iOS Simulator or physical device
- CocoaPods (`sudo gem install cocoapods`)

#### Android Development
- Android Studio with Android SDK 33+
- Android Emulator or physical device
- JDK 17 (`flutter config --jdk-dir <jdk17>`; Gradle 8.14 does not start on JDK 25)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/siutindei.git
cd siutindei
```

### 2. Navigate to the App

```bash
cd apps/siutindei_app
```

### 3. Install Dependencies

```bash
flutter pub get
```

### 4. Verify Setup

```bash
flutter doctor
```

Ensure all required components show checkmarks.

## Configuration

### Environment Variables

The app requires configuration for AWS Amplify services. Create environment variables or use `--dart-define`:

```bash
# Required: the Amplify configuration JSON (API, Auth). Startup throws
# "AMPLIFY_CONFIG is not set" without it.
AMPLIFY_CONFIG='<amplifyconfiguration JSON>'
AMPLIFY_API_KEY=your-api-key

# Optional
AMPLIFY_API_NAME=activitiesApi          # default
PUBLIC_WWW_BASE_URL=https://siutindei.com  # default
STAGING_SEARCH_DATA_ENABLED=false
STAGING_SEARCH_FIXTURE_URL=https://.../fixtures/activity_search_staging.json

# Firebase (see lib/config/firebase_config.dart)
FIREBASE_PROJECT_ID=your-project-id
```

### Running with Configuration

```bash
flutter run \
  --dart-define=AMPLIFY_CONFIG='<amplifyconfiguration JSON>' \
  --dart-define=AMPLIFY_API_KEY=your-api-key
```

See `lib/config/amplify_config.dart`, `site_links.dart`, and
`firebase_config.dart` for every `--dart-define` the app reads.

To build `AMPLIFY_CONFIG` from a deployed API stack instead of writing it
by hand (this is what `deploy-mobile.yml` and `deploy-ios.yml` do):

```bash
python3 scripts/deploy/build_amplify_config.py \
  --params backend/infrastructure/params/production.json \
  --output apps/siutindei_app/build/amplify-defines.json
flutter run --dart-define-from-file=build/amplify-defines.json \
  --dart-define=AMPLIFY_API_KEY=your-api-key
```

## Running the App

### iOS Simulator

```bash
# List available simulators
flutter devices

# Run on iOS Simulator
flutter run -d "iPhone 15"
```

### Android Emulator

```bash
# List available devices
flutter devices

# Run on Android Emulator
flutter run -d "emulator-5554"
```

### Web (Development Only)

```bash
flutter run -d chrome
```

## Project Structure Overview

```
lib/
├── main.dart              # Entry point
├── app.dart               # Root widget
├── config/                # Configuration
│   ├── amplify_config.dart
│   ├── constants.dart
│   └── tokens/            # Design tokens
├── core/                  # Shared utilities
│   ├── utils/             # Result, Command
│   └── widgets/           # Base widgets
├── domain/                # Business logic
│   ├── entities/
│   ├── repositories/
│   └── use_cases/
├── data/                  # Data access
│   ├── repositories/
│   └── mappers/
├── features/              # UI features
│   ├── search/
│   ├── activity_detail/
│   ├── organization/
│   └── auth/
├── viewmodels/            # State management
├── services/              # External services
└── models/                # Data models
```

## Development Workflow

### 1. Make Changes

Edit code in your preferred IDE (VS Code, Android Studio, IntelliJ).

### 2. Hot Reload

Press `r` in the terminal or save files to trigger hot reload.

### 3. Hot Restart

Press `R` in the terminal for a full restart (resets state).

### 4. Run Tests

```bash
# All tests
flutter test

# Specific test file
flutter test test/area_filter_options_test.dart

# With coverage
flutter test --coverage
```

### 5. Analyze Code

```bash
flutter analyze
```

### 6. Format Code

```bash
dart format lib test
```

## Common Tasks

### Adding a New Feature

1. Create feature directory:
   ```bash
   mkdir -p lib/features/my_feature/{screens,widgets}
   ```

2. Create barrel file:
   ```dart
   // lib/features/my_feature/my_feature.dart
   library;
   export 'screens/my_screen.dart';
   ```

3. Export from features.dart:
   ```dart
   export 'my_feature/my_feature.dart';
   ```

### Adding a New Entity

1. Create in `lib/domain/entities/`:
   ```dart
   class MyEntity {
     const MyEntity({required this.id, required this.name});
     final String id;
     final String name;
   }
   ```

2. Export from `entities.dart`

### Adding a New Use Case

1. Create in `lib/domain/use_cases/`:
   ```dart
   class MyUseCase {
     const MyUseCase(this._repository);
     final MyRepository _repository;
     
     Future<Result<MyEntity>> execute(String id) async {
       return _repository.getById(id);
     }
   }
   ```

2. Add provider in `lib/data/providers.dart`:
   ```dart
   final myUseCaseProvider = Provider<MyUseCase>((ref) {
     return MyUseCase(ref.watch(myRepositoryProvider));
   });
   ```

### Adding Design Tokens

1. Add primitive values in `primitive_tokens.dart`
2. Add semantic mapping in `semantic_tokens.dart`
3. Add component tokens in `component_tokens.dart`
4. Register in `token_registry.dart`

## Troubleshooting

### Flutter SDK Not Found

```bash
# Add to your shell profile
export PATH="$PATH:/path/to/flutter/bin"
```

### iOS Build Fails

```bash
cd ios
pod install --repo-update
cd ..
flutter clean
flutter pub get
```

### Android Build Fails

```bash
flutter clean
flutter pub get
cd android
./gradlew clean
cd ..
```

### Dependencies Not Resolving

```bash
flutter pub cache repair
flutter pub get
```

### Hot Reload Not Working

Try hot restart (`R`) or full restart:
```bash
flutter run
```

## IDE Setup

### VS Code

Install extensions:
- Flutter
- Dart
- Error Lens (optional)

Settings (`.vscode/settings.json`):
```json
{
  "dart.flutterSdkPath": "/path/to/flutter",
  "editor.formatOnSave": true,
  "dart.lineLength": 80
}
```

### Android Studio / IntelliJ

1. Install Flutter and Dart plugins
2. Configure Flutter SDK path in Preferences
3. Enable "Format on save"

## Next Steps

- Read the [Architecture Overview](../README.md#architecture-overview)
- Explore the [Design Token System](design/tokens.md)
- Learn about [ViewModels](viewmodels/README.md)
- Check out [Feature Structure](features/README.md)

## Getting Help

- Check existing documentation in `docs/`
- Review code comments and docstrings
- Ask in team chat/Slack
- Create an issue for bugs
