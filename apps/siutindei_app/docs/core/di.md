# Dependency Injection

The `ServiceLocator` provides centralized dependency management following Flutter architecture recommendations.

## Overview

Features:
- Riverpod-based dependency injection
- Centralized dependency graph documentation
- Easy test overrides
- Clear provider relationships

## Location

```
lib/core/di/
├── di.dart              # Barrel file
└── service_locator.dart # Service locator and providers
```

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│  ┌─────────────┐                                            │
│  │ ViewModels  │ ◄─── Uses use cases                        │
│  └──────┬──────┘                                            │
├─────────┼───────────────────────────────────────────────────┤
│         ▼                Domain Layer                        │
│  ┌─────────────┐                                            │
│  │  Use Cases  │ ◄─── Uses repository interfaces            │
│  └──────┬──────┘                                            │
│         │                                                    │
│  ┌──────▼──────┐                                            │
│  │ Repositories│ ◄─── Interface definitions                 │
│  │ (Interface) │                                            │
│  └─────────────┘                                            │
├─────────────────────────────────────────────────────────────┤
│                       Data Layer                             │
│  ┌─────────────┐                                            │
│  │ Repositories│ ◄─── Implements interfaces                 │
│  │   (Impl)    │                                            │
│  └──────┬──────┘                                            │
│         │                                                    │
│  ┌──────▼──────┐  ┌─────────────┐                          │
│  │   Services  │  │    Cache    │                          │
│  │  (API, etc) │  │   Manager   │                          │
│  └─────────────┘  └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

## Provider Definitions

### Services (Leaf Dependencies)

```dart
// lib/services/service_providers.dart
final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService();
});

final apiServiceProvider = Provider<ApiService>((ref) {
  return ApiService(
    ref.watch(authServiceProvider),
    ref.watch(deviceAttestationServiceProvider),
  );
});
```

### Repositories

```dart
// lib/data/providers.dart
final activityRepositoryProvider = Provider<ActivityRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return ActivityRepositoryImpl(apiService);
});
```

### Use Cases

```dart
// lib/data/providers.dart
final searchActivitiesUseCaseProvider = Provider<SearchActivitiesUseCase>((ref) {
  final repository = ref.watch(activityRepositoryProvider);
  return SearchActivitiesUseCase(repository);
});
```

### ViewModels

```dart
// lib/viewmodels/activities_viewmodel.dart
final activitiesViewModelProvider =
    NotifierProvider<ActivitiesViewModel, ActivitiesState>(
      ActivitiesViewModel.new,
    );
```

## ServiceLocator Class

```dart
class ServiceLocator {
  ServiceLocator._();

  /// Default overrides (empty in production)
  static List<Override> get defaultOverrides => [];

  /// Creates overrides for testing
  static List<Override> testOverrides({
    ActivityRepository? activityRepository,
    OrganizationRepository? organizationRepository,
    SearchActivitiesUseCase? searchUseCase,
    LoadMoreActivitiesUseCase? loadMoreUseCase,
  }) {
    return [
      if (activityRepository != null)
        activityRepositoryProvider.overrideWithValue(activityRepository),
      if (organizationRepository != null)
        organizationRepositoryProvider.overrideWithValue(organizationRepository),
      if (searchUseCase != null)
        searchActivitiesUseCaseProvider.overrideWithValue(searchUseCase),
      if (loadMoreUseCase != null)
        loadMoreActivitiesUseCaseProvider.overrideWithValue(loadMoreUseCase),
    ];
  }
}
```

## Usage

### In App Root

```dart
void main() {
  runApp(
    ProviderScope(
      overrides: ServiceLocator.defaultOverrides,
      child: const MyApp(),
    ),
  );
}
```

### In Widgets

```dart
class MyWidget extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Access dependencies through providers
    final repository = ref.watch(activityRepositoryProvider);
    final viewModel = ref.watch(activitiesViewModelProvider.notifier);
    
    // ...
  }
}
```

### In Tests

```dart
testWidgets('SearchScreen shows results', (tester) async {
  final mockRepository = MockActivityRepository();
  when(mockRepository.searchActivities(any)).thenAnswer(
    (_) async => Result.ok(mockResults),
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: ServiceLocator.testOverrides(
        activityRepository: mockRepository,
      ),
      child: MaterialApp(home: SearchScreen()),
    ),
  );

  // Test assertions...
});
```

### Unit Tests

```dart
void main() {
  test('ViewModel uses injected use case', () async {
    final mockUseCase = MockSearchActivitiesUseCase();
    when(mockUseCase.execute(any)).thenAnswer(
      (_) async => Result.ok(mockResults),
    );

    final container = ProviderContainer(
      overrides: [
        searchActivitiesUseCaseProvider.overrideWithValue(mockUseCase),
      ],
    );

    final viewModel = container.read(activitiesViewModelProvider.notifier);
    await viewModel.search(SearchFilters());

    verify(mockUseCase.execute(any)).called(1);
  });
}
```

## Best Practices

### 1. Keep Providers Simple

```dart
// Good - simple, focused provider
final activityRepositoryProvider = Provider<ActivityRepository>((ref) {
  return ActivityRepositoryImpl(ref.watch(apiServiceProvider));
});

// Avoid - complex logic in provider
final activityRepositoryProvider = Provider<ActivityRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  final cache = CacheManager.instance;
  final logger = Logger();
  // ... lots of setup
  return ActivityRepositoryImpl(apiService, cache, logger);
});
```

### 2. Resolve Dependencies in `build()`

```dart
// Good - watch use-case providers once in build(); tests override them
class ActivitiesViewModel extends Notifier<ActivitiesState> {
  late final SearchActivitiesUseCase _searchUseCase;

  @override
  ActivitiesState build() {
    _searchUseCase = ref.watch(searchActivitiesUseCaseProvider);
    return ActivitiesState.initial;
  }
}
```

### 3. Document Dependencies

```dart
/// Provider for [ActivitiesViewModel].
///
/// Dependencies:
/// - [searchActivitiesUseCaseProvider]
/// - [loadMoreActivitiesUseCaseProvider]
final activitiesViewModelProvider =
    NotifierProvider<ActivitiesViewModel, ActivitiesState>(
      ActivitiesViewModel.new,
    );
```

## Related

- [ViewModels](../viewmodels/README.md) - Dependency consumers
- [Use Cases](../domain/use_cases.md) - Business logic providers
- [Repositories](../data/repositories.md) - Data access providers
- [Architecture Recommendations](../architecture-recommendations.md) - DI patterns
