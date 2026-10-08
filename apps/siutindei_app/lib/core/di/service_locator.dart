import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/providers.dart';
import '../../domain/repositories/repositories.dart';
import '../../domain/use_cases/use_cases.dart';
import '../cache/cache_manager.dart';

/// Service locator for centralized dependency management.
///
/// Follows Flutter architecture recommendations for dependency injection:
/// - Single source of truth for dependencies
/// - Easy testing through provider overrides
/// - Clear dependency graph
///
/// See: https://docs.flutter.dev/app-architecture/recommendations
///
/// ## Usage
///
/// Access services through Riverpod providers:
/// ```dart
/// final repository = ref.watch(activityRepositoryProvider);
/// final useCase = ref.watch(searchActivitiesUseCaseProvider);
/// ```
///
/// ## Testing
///
/// Override providers for testing:
/// ```dart
/// final container = ProviderContainer(
///   overrides: [
///     activityRepositoryProvider.overrideWithValue(MockRepository()),
///   ],
/// );
/// ```
class ServiceLocator {
  ServiceLocator._();

  /// Creates a ProviderContainer with test overrides.
  ///
  /// Example:
  /// ```dart
  /// final container = ServiceLocator.createTestContainer(
  ///   activityRepository: MockActivityRepository(),
  /// );
  /// ```
  static ProviderContainer createTestContainer({
    ActivityRepository? activityRepository,
    OrganizationRepository? organizationRepository,
    SearchActivitiesUseCase? searchUseCase,
    LoadMoreActivitiesUseCase? loadMoreUseCase,
  }) {
    return ProviderContainer(
      overrides: [
        if (activityRepository != null)
          activityRepositoryProvider.overrideWithValue(activityRepository),
        if (organizationRepository != null)
          organizationRepositoryProvider.overrideWithValue(
            organizationRepository,
          ),
        if (searchUseCase != null)
          searchActivitiesUseCaseProvider.overrideWithValue(searchUseCase),
        if (loadMoreUseCase != null)
          loadMoreActivitiesUseCaseProvider.overrideWithValue(loadMoreUseCase),
      ],
    );
  }
}

/// Provider for CacheManager instance.
final cacheManagerProvider = Provider<CacheManager>((ref) {
  return CacheManager.instance;
});

/// Dependency graph documentation.
///
/// ```
/// ┌─────────────────────────────────────────────────────────────┐
/// │                     Presentation Layer                       │
/// │  ┌─────────────┐                                            │
/// │  │ ViewModels  │ ◄─── Uses use cases for business logic     │
/// │  └──────┬──────┘                                            │
/// ├─────────┼───────────────────────────────────────────────────┤
/// │         ▼                Domain Layer                        │
/// │  ┌─────────────┐                                            │
/// │  │  Use Cases  │ ◄─── Uses repository interfaces            │
/// │  └──────┬──────┘                                            │
/// │         │                                                    │
/// │  ┌──────▼──────┐                                            │
/// │  │ Repositories│ ◄─── Interface definitions                 │
/// │  │ (Interface) │                                            │
/// │  └─────────────┘                                            │
/// ├─────────────────────────────────────────────────────────────┤
/// │                       Data Layer                             │
/// │  ┌─────────────┐                                            │
/// │  │ Repositories│ ◄─── Implements interfaces                 │
/// │  │   (Impl)    │                                            │
/// │  └──────┬──────┘                                            │
/// │         │                                                    │
/// │  ┌──────▼──────┐  ┌─────────────┐                          │
/// │  │   Services  │  │    Cache    │                          │
/// │  │  (API, etc) │  │   Manager   │                          │
/// │  └─────────────┘  └─────────────┘                          │
/// └─────────────────────────────────────────────────────────────┘
/// ```
class DependencyGraph {
  DependencyGraph._();

  /// Providers in order of dependency (leaf to root).
  static const providers = '''
Services (leaf dependencies):
- authServiceProvider
- deviceAttestationServiceProvider
- amplifyServiceProvider
- apiServiceProvider
- cacheManagerProvider

Repositories:
- activityRepositoryProvider (depends on apiService, cacheManager)
- organizationRepositoryProvider (depends on apiService, cacheManager)

Use Cases:
- searchActivitiesUseCaseProvider (depends on activityRepository)
- loadMoreActivitiesUseCaseProvider (depends on activityRepository)
- getActivityUseCaseProvider (depends on activityRepository)
- getOrganizationUseCaseProvider (depends on organizationRepository)

ViewModels:
- activitiesViewModelProvider (depends on use cases)
- authViewModelProvider (depends on authService)
''';
}
