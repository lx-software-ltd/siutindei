# Architecture Recommendations Compliance

This document details how the Siutindei app implements Flutter's architecture recommendations from [docs.flutter.dev/app-architecture/recommendations](https://docs.flutter.dev/app-architecture/recommendations).

## Key Recommendations Implemented

### 1. Separate UI from State and Logic

**Recommendation**: Keep UI code separate from business logic and state management.

**Implementation**:
- **UI Layer** (`features/`): Contains only widgets that render UI
- **ViewModel Layer** (`viewmodels/`): Manages state with Riverpod `Notifier`
- **Domain Layer** (`domain/`): Contains business logic in use cases
- **Data Layer** (`data/`): Handles data access and transformation

```dart
// UI only handles rendering
class SearchScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(activitiesViewModelProvider);
    // Render based on state
  }
}

// ViewModel handles state
class ActivitiesViewModel extends Notifier<ActivitiesState> {
  Future<void> search(SearchFilters filters) async {
    state = state.copyWith(isLoading: true);
    final result = await _searchUseCase.execute(filters);
    // Update state based on result
  }
}
```

### 2. Use a Single Source of Truth

**Recommendation**: Each piece of data should have a single source of truth.

**Implementation**:
- ViewModels are the single source of truth for UI state
- Repositories are the single source of truth for data
- CacheManager provides centralized caching

```dart
// ActivitiesState is the single source for search state
@immutable
class ActivitiesState {
  final SearchResultsEntity results;
  final SearchFilters filters;
  final bool isLoading;
  final String? errorMessage;
}

// Repository is single source for activity data
abstract interface class ActivityRepository {
  Future<Result<SearchResultsEntity>> searchActivities(SearchFilters filters);
}
```

### 3. Use Unidirectional Data Flow

**Recommendation**: Data should flow in one direction from source to UI.

**Implementation**:
```
User Action → ViewModel Method → Use Case → Repository → API
                                                          ↓
UI ← State Update ← ViewModel ← Result ← Repository ← Response
```

```dart
// User triggers action
ElevatedButton(
  onPressed: () => ref.read(viewModelProvider.notifier).search(filters),
)

// Data flows through layers
viewModel.search(filters)
  → useCase.execute(filters)
    → repository.searchActivities(filters)
      → apiService.search(filters)
        → Result<SearchResultsEntity>
      → cache.set(key, result)
    → Result<SearchResultsEntity>
  → state = state.copyWith(results: result)
→ UI rebuilds with new state
```

### 4. Use Immutable Data

**Recommendation**: Data objects should be immutable.

**Implementation**:
- All entities are immutable with `final` fields
- State objects use `copyWith` for updates
- `@immutable` annotation enforced

```dart
@immutable
class ActivityEntity {
  const ActivityEntity({
    required this.id,
    required this.name,
  });

  final String id;
  final String name;
}

@immutable
class ActivitiesState {
  // All fields final, use copyWith for updates
  ActivitiesState copyWith({...}) { ... }
}
```

### 5. Use Result Types for Error Handling

**Recommendation**: Use explicit result types instead of exceptions for expected errors.

**Implementation**:
- `Result<T>` sealed class with `Ok` and `Error` variants
- Pattern matching for handling results
- Custom `AppException` hierarchy for typed errors

```dart
sealed class Result<T> {
  const factory Result.ok(T value) = Ok<T>;
  const factory Result.error(Exception error) = Error<T>;
}

// Usage with pattern matching
final result = await useCase.execute(filters);
switch (result) {
  case Ok(value: final data):
    state = state.copyWith(results: data);
  case Error(error: final e):
    state = state.copyWith(errorMessage: e.displayMessage);
}
```

### 6. Repository as Data Source of Truth

**Recommendation**: Repositories should be the single source of truth for data.

**Implementation**:
- Repository interfaces in domain layer
- Implementations in data layer with caching
- Stale-while-revalidate pattern for better UX

```dart
class ActivityRepositoryImpl implements ActivityRepository {
  @override
  Future<Result<SearchResultsEntity>> searchActivities(
    SearchFilters filters,
  ) async {
    return _cache.getOrFetch<SearchResultsEntity>(
      key: cacheKey,
      policy: CachePolicy.api,
      fetch: () => _fetchSearchResults(filters),
    );
  }
}
```

### 7. Expose Loading and Error States

**Recommendation**: UI should handle loading and error states explicitly.

**Implementation**:
- State includes `isLoading`, `isLoadingMore`, `errorMessage`
- UI renders different views based on state
- Retry capabilities for recoverable errors

```dart
class ActivitiesState {
  final bool isLoading;
  final bool isLoadingMore;
  final String? errorMessage;
  
  bool get hasError => errorMessage != null;
}

// UI handles all states
if (state.isLoading) return LoadingIndicator();
if (state.hasError) return ErrorView(onRetry: viewModel.retry);
return ResultsList(items: state.items);
```

### 8. Use Dependency Injection

**Recommendation**: Use dependency injection for testability.

**Implementation**:
- Riverpod providers for all dependencies
- Provider injection in ViewModels (`build()` watches use-case providers) and constructor injection in Use Cases
- ServiceLocator for centralized dependency management

```dart
final activitiesViewModelProvider =
    NotifierProvider<ActivitiesViewModel, ActivitiesState>(
      ActivitiesViewModel.new,
    );

// Testing with overrides
final container = ProviderContainer(
  overrides: ServiceLocator.testOverrides(
    activityRepository: MockActivityRepository(),
  ),
);
```

### 9. Cache for Offline-First

**Recommendation**: Implement caching for offline support and better performance.

**Implementation**:
- `CacheManager` with configurable policies
- Stale-while-revalidate pattern
- Cache invalidation strategies

```dart
class CachePolicy {
  final Duration maxAge;
  final bool staleWhileRevalidate;
  
  static const api = CachePolicy(
    maxAge: Duration(minutes: 5),
    staleWhileRevalidate: true,
  );
}

// Repository uses cache
return _cache.getOrFetch<SearchResultsEntity>(
  key: cacheKey,
  policy: CachePolicy.api,
  fetch: () => _fetchFromApi(filters),
);
```

### 10. Typed Exceptions

**Recommendation**: Use typed exceptions for different error scenarios.

**Implementation**:
- `AppException` sealed class hierarchy
- Specific exception types: `NetworkException`, `DataException`, `AuthException`, etc.
- Display-friendly messages and retry information

```dart
sealed class AppException implements Exception {
  String get displayMessage;
  bool get isRetryable;
}

final class NetworkException extends AppException {
  factory NetworkException.noConnection() { ... }
  factory NetworkException.timeout() { ... }
  factory NetworkException.serverError([int? statusCode]) { ... }
}
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Screens   │  │   Widgets   │  │ ViewModels  │         │
│  │  (UI Only)  │  │  (UI Only)  │  │  (State)    │         │
│  └──────┬──────┘  └─────────────┘  └──────┬──────┘         │
│         │              watches              │                │
│         └──────────────────────────────────┘                │
├─────────────────────────────────────────────────────────────┤
│                      Domain Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Entities   │  │ Repositories│  │  Use Cases  │         │
│  │ (Immutable) │  │ (Interface) │  │  (Logic)    │         │
│  └─────────────┘  └──────┬──────┘  └──────┬──────┘         │
│                          │                 │                 │
├──────────────────────────┼─────────────────┼─────────────────┤
│                      Data│Layer            │                 │
│  ┌─────────────┐  ┌──────▼──────┐  ┌──────▼──────┐         │
│  │   Mappers   │  │ Repositories│  │    Cache    │         │
│  │             │  │   (Impl)    │  │   Manager   │         │
│  └─────────────┘  └──────┬──────┘  └─────────────┘         │
│                          │                                   │
│                   ┌──────▼──────┐                           │
│                   │   Services  │                           │
│                   │  (API, etc) │                           │
│                   └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

## Testing Strategy

Following architecture recommendations enables easy testing:

```dart
// Unit test use case
test('validates age filter', () async {
  final useCase = SearchActivitiesUseCase(MockRepository());
  final result = await useCase.execute(SearchFilters(age: -1));
  expect(result.isError, isTrue);
});

// Unit test repository
test('returns cached data when available', () async {
  final cache = MockCacheManager();
  when(cache.get(any)).thenReturn(cachedData);
  
  final repo = ActivityRepositoryImpl(mockApi, cacheManager: cache);
  final result = await repo.searchActivities(filters);
  
  expect(result.valueOrNull, equals(cachedData));
  verifyNever(mockApi.search(any)); // API not called
});

// Widget test with provider overrides
testWidgets('shows loading state', (tester) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: ServiceLocator.testOverrides(
        searchUseCase: MockSearchUseCase(),
      ),
      child: MaterialApp(home: SearchScreen()),
    ),
  );
});
```

## Related Documentation

- [Architecture Guide](../README.md#architecture-overview)
- [Core Utilities](core/result.md)
- [Domain Layer](domain/entities.md)
- [Data Layer](data/repositories.md)
- [ViewModels](viewmodels/README.md)
