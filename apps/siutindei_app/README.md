# Siutindei App

A Flutter mobile application for searching and discovering activities for children. Built following Flutter's recommended app architecture guidelines.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Layer Documentation](#layer-documentation)
- [Design System](#design-system)
- [State Management](#state-management)
- [Testing](#testing)

## Architecture Overview

This app follows the [Flutter App Architecture Guide](https://docs.flutter.dev/app-architecture/guide) and [Architecture Recommendations](https://docs.flutter.dev/app-architecture/recommendations) with a layered architecture that separates concerns and promotes testability.

See **[Architecture Recommendations Compliance](docs/architecture-recommendations.md)** for detailed implementation notes.

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Screens   │  │   Widgets   │  │ ViewModels  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                      Domain Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Entities   │  │ Repositories│  │  Use Cases  │         │
│  │             │  │ (Interfaces)│  │             │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                       Data Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Repositories│  │   Mappers   │  │  Services   │         │
│  │   (Impl)    │  │             │  │             │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                       Core Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Result    │  │   Command   │  │Base Widgets │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **Unidirectional Data Flow**: Data flows from the data layer through domain to presentation
2. **Separation of Concerns**: Each layer has a specific responsibility
3. **Dependency Inversion**: Higher layers depend on abstractions, not implementations
4. **Immutable State**: All state objects are immutable
5. **Type-Safe Error Handling**: Using `Result<T>` for all async operations
6. **Single Source of Truth**: ViewModels for UI state, Repositories for data
7. **Offline-First**: Caching with stale-while-revalidate pattern
8. **Typed Exceptions**: Custom exception hierarchy for specific error handling

## Project Structure

```
lib/
├── main.dart                 # App entry point
├── app.dart                  # Root widget with providers
│
├── config/                   # Configuration
│   ├── amplify_config.dart   # AWS Amplify configuration
│   ├── firebase_config.dart  # Firebase configuration
│   ├── constants.dart        # Business constants
│   └── tokens/               # Design token system
│       ├── primitive_tokens.dart
│       ├── semantic_tokens.dart
│       ├── component_tokens.dart
│       └── token_registry.dart
│
├── core/                     # Shared utilities
│   ├── cache/
│   │   └── cache_manager.dart # Caching with policies
│   ├── di/
│   │   └── service_locator.dart # Dependency injection
│   ├── exceptions/
│   │   └── app_exceptions.dart # Typed exceptions
│   ├── utils/
│   │   ├── result.dart       # Result<T> type
│   │   └── command.dart      # Command pattern
│   └── widgets/
│       ├── base_card.dart
│       ├── base_avatar.dart
│       └── base_badge.dart
│
├── domain/                   # Business logic
│   ├── entities/             # Business objects
│   │   ├── activity.dart
│   │   └── search.dart
│   ├── repositories/         # Repository interfaces
│   │   └── activity_repository.dart
│   └── use_cases/            # Business operations
│       ├── search_activities_use_case.dart
│       └── get_activity_use_case.dart
│
├── data/                     # Data access
│   ├── repositories/         # Repository implementations
│   │   └── activity_repository_impl.dart
│   ├── mappers/              # Entity mappers
│   │   └── activity_mapper.dart
│   └── providers.dart        # DI providers
│
├── features/                 # Feature modules
│   ├── search/
│   │   ├── screens/
│   │   ├── utils/
│   │   └── widgets/
│   ├── home_wizard/
│   ├── activity_detail/
│   ├── organization/
│   └── auth/
│
├── viewmodels/               # State management
│   ├── activities_viewmodel.dart
│   └── auth_viewmodel.dart
│
├── services/                 # External services
│   ├── api_service.dart
│   ├── auth_service.dart
│   └── service_providers.dart
│
└── models/                   # Legacy data models
    └── activity_models.dart
```

## Getting Started

### Prerequisites

- Flutter 3.41+ (stable)
- Dart 3.10.3+ (`pubspec.yaml` `sdk: ">=3.10.3 <4.0.0"`)
- Android: JDK 17 (Gradle 8.14 does not start on JDK 25)
- iOS: Xcode 14+
- Android: Android Studio with SDK 33+

### Installation

1. Clone the repository
2. Navigate to the app directory:
   ```bash
   cd apps/siutindei_app
   ```
3. Install dependencies:
   ```bash
   flutter pub get
   ```
4. Configure environment (see [Configuration](#configuration))
5. Run the app:
   ```bash
   flutter run
   ```

### Configuration

The app requires configuration for AWS Amplify and Firebase:

```bash
# Development
flutter run --dart-define=AMPLIFY_CONFIG='<amplifyconfiguration JSON>' \
            --dart-define=AMPLIFY_API_KEY=your-api-key \
            --dart-define=AMPLIFY_API_NAME=activitiesApi
```

See `lib/config/` for all configuration options. CI generates
`AMPLIFY_CONFIG` from the `lxsoftware-siutindei` stack outputs with
`scripts/deploy/build_amplify_config.py`; see
[Getting started](docs/getting-started.md#running-with-configuration).

## Layer Documentation

### Core Layer

The core layer provides foundational utilities used across all other layers.

- **[Result Type](docs/core/result.md)**: Type-safe error handling
- **[Command Pattern](docs/core/command.md)**: Async operation management
- **[Base Widgets](docs/core/widgets.md)**: Token-aware UI components
- **[Cache Manager](docs/core/cache.md)**: Offline-first caching
- **[Exceptions](docs/core/exceptions.md)**: Typed exception hierarchy
- **[Service Locator](docs/core/di.md)**: Dependency injection

### Domain Layer

The domain layer contains pure business logic with no framework dependencies.

- **[Entities](docs/domain/entities.md)**: Business objects
- **[Repositories](docs/domain/repositories.md)**: Data access contracts
- **[Use Cases](docs/domain/use_cases.md)**: Business operations

### Data Layer

The data layer handles all external data access.

- **[Repositories](docs/data/repositories.md)**: Implementation details
- **[Mappers](docs/data/mappers.md)**: Data transformation

### Presentation Layer

The presentation layer contains all UI-related code.

- **[Features](docs/features/README.md)**: Feature module structure
- **[ViewModels](docs/viewmodels/README.md)**: State management

## Design System

The app uses a hierarchical design token system for consistent theming:

```
Primitive Tokens → Semantic Tokens → Component Tokens
```

- **[Design Tokens Overview](docs/design/tokens.md)**
- **[Theme Customization](docs/design/customization.md)**
- **[JSON Token Ingestion](docs/design/json-tokens.md)**

## State Management

State is managed using [Riverpod](https://riverpod.dev/) with the following patterns:

1. **ViewModels** extend `Notifier<State>` (Riverpod 3) for feature state; `AuthViewModel` still uses the legacy `StateNotifier`
2. **Providers** are used for dependency injection
3. **Selectors** minimize widget rebuilds

Example:
```dart
// Watch specific state slice
final items = ref.watch(activitiesViewModelProvider.select((s) => s.items));

// Read ViewModel for actions
ref.read(activitiesViewModelProvider.notifier).search(filters);
```

## Testing

### Running Tests

```bash
# Unit tests
flutter test

# With coverage
flutter test --coverage
```

### Test Structure

```
test/
├── area_filter_chips_test.dart
├── area_filter_options_test.dart
├── geographic_area_tree_test.dart
└── home_wizard_choices_test.dart

There is no `integration_test/` suite yet.
```

## Performance

The app follows [Flutter performance best practices](https://docs.flutter.dev/perf/best-practices):

- Granular Riverpod selectors to minimize rebuilds
- Widget extraction for isolation
- `RepaintBoundary` for expensive widgets
- Cached layout objects (BorderRadius, etc.)
- `ListView.builder` with `scrollCacheExtent` (Flutter 3.41+)
- Image caching with `cacheWidth`/`cacheHeight`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

See [LICENSE](../../LICENSE) for details.
