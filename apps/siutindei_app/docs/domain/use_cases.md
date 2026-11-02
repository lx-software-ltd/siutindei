# Use Cases

Use cases encapsulate application-specific business rules. They orchestrate the flow of data and direct entities to use their business logic.

## Overview

Use cases:
- Contain business logic
- Validate inputs
- Coordinate between repositories
- Return `Result<T>` for type-safe error handling

## Location

```
lib/domain/use_cases/
├── use_cases.dart                  # Barrel file
├── search_activities_use_case.dart # Search operations
└── get_activity_use_case.dart      # Get operations
```

## Design Principles

1. **Single Purpose**: One use case per business operation
2. **Input Validation**: Validate before calling repositories
3. **Domain Logic**: Contains rules that aren't in entities
4. **Repository Coordination**: May use multiple repositories
5. **No UI Concerns**: Framework-agnostic

## SearchActivitiesUseCase

Handles activity search with input validation.

```dart
class SearchActivitiesUseCase {
  const SearchActivitiesUseCase(this._repository);

  final ActivityRepository _repository;

  /// Executes the activity search.
  ///
  /// Validates filters before performing the search.
  /// Returns [SearchResultsEntity] on success.
  Future<Result<SearchResultsEntity>> execute(SearchFilters filters) async {
    // Validate filters
    final validationError = _validateFilters(filters);
    if (validationError != null) {
      return Result.error(validationError);
    }

    return _repository.searchActivities(filters);
  }

  /// Validates search filters.
  Exception? _validateFilters(SearchFilters filters) {
    // Age validation
    if (filters.age != null && (filters.age! < 0 || filters.age! > 100)) {
      return ArgumentError('Age must be between 0 and 100');
    }

    // Price validation
    if (filters.priceMin != null && filters.priceMin! < 0) {
      return ArgumentError('Minimum price cannot be negative');
    }
    if (filters.priceMax != null && filters.priceMax! < 0) {
      return ArgumentError('Maximum price cannot be negative');
    }
    if (filters.priceMin != null &&
        filters.priceMax != null &&
        filters.priceMin! > filters.priceMax!) {
      return ArgumentError('Minimum price cannot exceed maximum price');
    }

    // Time validation
    if (filters.startMinutesUtc != null &&
        (filters.startMinutesUtc! < 0 || filters.startMinutesUtc! > 1440)) {
      return ArgumentError('Start time must be between 0 and 1440 minutes');
    }

    // Day of week validation
    if (filters.dayOfWeekUtc != null &&
        (filters.dayOfWeekUtc! < 0 || filters.dayOfWeekUtc! > 6)) {
      return ArgumentError('Day of week must be between 0 and 6');
    }

    // Limit validation
    if (filters.limit < 1 || filters.limit > 100) {
      return ArgumentError('Limit must be between 1 and 100');
    }

    return null;
  }
}
```

## LoadMoreActivitiesUseCase

Handles pagination by appending new results.

```dart
class LoadMoreActivitiesUseCase {
  const LoadMoreActivitiesUseCase(this._repository);

  final ActivityRepository _repository;

  /// Loads the next page of results.
  ///
  /// [currentFilters] - The filters with the cursor for the next page.
  /// [existingResults] - The current results to append to.
  ///
  /// Returns combined results on success.
  Future<Result<SearchResultsEntity>> execute(
    SearchFilters currentFilters,
    SearchResultsEntity existingResults,
  ) async {
    if (currentFilters.cursor == null) {
      return Result.error(StateError('No more results to load'));
    }

    final result = await _repository.searchActivities(currentFilters);

    return result.map((newResults) => SearchResultsEntity(
          items: [...existingResults.items, ...newResults.items],
          nextCursor: newResults.nextCursor,
        ));
  }
}
```

## GetActivityUseCase

Retrieves detailed information about a specific activity.

```dart
class GetActivityUseCase {
  const GetActivityUseCase(this._repository);

  final ActivityRepository _repository;

  /// Executes the use case to get activity details.
  ///
  /// [activityId] - The ID of the activity to retrieve.
  ///
  /// Returns [ActivitySearchResultEntity] on success.
  Future<Result<ActivitySearchResultEntity>> execute(String activityId) async {
    if (activityId.isEmpty) {
      return Result.error(ArgumentError('Activity ID cannot be empty'));
    }

    return _repository.getActivity(activityId);
  }
}
```

## GetOrganizationUseCase

Retrieves organization details.

```dart
class GetOrganizationUseCase {
  const GetOrganizationUseCase(this._repository);

  final OrganizationRepository _repository;

  Future<Result<OrganizationEntity>> execute(String organizationId) async {
    if (organizationId.isEmpty) {
      return Result.error(ArgumentError('Organization ID cannot be empty'));
    }

    return _repository.getOrganization(organizationId);
  }
}
```

## Using Use Cases

### In ViewModels

```dart
class ActivitiesViewModel extends Notifier<ActivitiesState> {
  late final SearchActivitiesUseCase _searchUseCase;
  late final LoadMoreActivitiesUseCase _loadMoreUseCase;

  @override
  ActivitiesState build() {
    _searchUseCase = ref.watch(searchActivitiesUseCaseProvider);
    _loadMoreUseCase = ref.watch(loadMoreActivitiesUseCaseProvider);
    return ActivitiesState.initial;
  }

  Future<void> search(SearchFilters filters) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _searchUseCase.execute(filters.withoutCursor());

    switch (result) {
      case Ok(value: final data):
        state = state.copyWith(results: data, isLoading: false);
      case Error(error: final e):
        state = state.copyWith(
          isLoading: false,
          errorMessage: _formatError(e),
        );
    }
  }

  Future<void> loadMore() async {
    if (state.isLoadingMore || !state.hasMore) return;

    state = state.copyWith(isLoadingMore: true);

    final filtersWithCursor = state.filters.copyWith(
      cursor: state.results.nextCursor,
    );

    final result = await _loadMoreUseCase.execute(
      filtersWithCursor,
      state.results,
    );

    switch (result) {
      case Ok(value: final data):
        state = state.copyWith(results: data, isLoadingMore: false);
      case Error(error: final e):
        state = state.copyWith(
          isLoadingMore: false,
          errorMessage: _formatError(e),
        );
    }
  }
}
```

### With Dependency Injection

```dart
// Provider definitions
final searchActivitiesUseCaseProvider = Provider<SearchActivitiesUseCase>((ref) {
  final repository = ref.watch(activityRepositoryProvider);
  return SearchActivitiesUseCase(repository);
});

final loadMoreActivitiesUseCaseProvider = Provider<LoadMoreActivitiesUseCase>((ref) {
  final repository = ref.watch(activityRepositoryProvider);
  return LoadMoreActivitiesUseCase(repository);
});

// ViewModel provider
final activitiesViewModelProvider =
    NotifierProvider<ActivitiesViewModel, ActivitiesState>(
      ActivitiesViewModel.new,
    );
```

## Creating New Use Cases

Follow this template:

```dart
/// Use case for [operation description].
///
/// [Detailed description of what this use case does]
class MyOperationUseCase {
  const MyOperationUseCase(this._repository);

  final MyRepository _repository;

  /// Executes the use case.
  ///
  /// [param1] - Description.
  /// [param2] - Description.
  ///
  /// Returns [ReturnType] on success.
  /// Returns error if [error conditions].
  Future<Result<ReturnType>> execute(
    ParamType1 param1,
    ParamType2 param2,
  ) async {
    // 1. Validate inputs
    if (param1.isEmpty) {
      return Result.error(ArgumentError('param1 cannot be empty'));
    }

    // 2. Apply business rules
    final processedParam = _applyBusinessRule(param1);

    // 3. Coordinate repositories
    final result = await _repository.operation(processedParam);

    // 4. Transform if needed
    return result.map(_transformResult);
  }

  // Private helper methods
  ParamType1 _applyBusinessRule(ParamType1 param) { ... }
  ReturnType _transformResult(RawType raw) { ... }
}
```

## Testing Use Cases

```dart
void main() {
  group('SearchActivitiesUseCase', () {
    late MockActivityRepository mockRepository;
    late SearchActivitiesUseCase useCase;

    setUp(() {
      mockRepository = MockActivityRepository();
      useCase = SearchActivitiesUseCase(mockRepository);
    });

    test('returns error for invalid age', () async {
      final result = await useCase.execute(SearchFilters(age: -5));

      expect(result.isError, isTrue);
      expect(result.errorOrNull, isA<ArgumentError>());
      verifyNever(mockRepository.searchActivities(any));
    });

    test('returns error for invalid price range', () async {
      final result = await useCase.execute(
        SearchFilters(priceMin: 100, priceMax: 50),
      );

      expect(result.isError, isTrue);
      expect(
        result.errorOrNull.toString(),
        contains('Minimum price cannot exceed maximum price'),
      );
    });

    test('delegates to repository for valid filters', () async {
      when(mockRepository.searchActivities(any)).thenAnswer(
        (_) async => Result.ok(SearchResultsEntity.empty),
      );

      final result = await useCase.execute(SearchFilters(age: 8));

      expect(result.isOk, isTrue);
      verify(mockRepository.searchActivities(any)).called(1);
    });
  });

  group('LoadMoreActivitiesUseCase', () {
    late MockActivityRepository mockRepository;
    late LoadMoreActivitiesUseCase useCase;

    setUp(() {
      mockRepository = MockActivityRepository();
      useCase = LoadMoreActivitiesUseCase(mockRepository);
    });

    test('returns error when no cursor', () async {
      final result = await useCase.execute(
        SearchFilters(), // No cursor
        SearchResultsEntity.empty,
      );

      expect(result.isError, isTrue);
      expect(result.errorOrNull, isA<StateError>());
    });

    test('combines existing and new results', () async {
      final existing = SearchResultsEntity(
        items: [mockItem1],
        nextCursor: 'cursor1',
      );
      final newResults = SearchResultsEntity(
        items: [mockItem2],
        nextCursor: 'cursor2',
      );

      when(mockRepository.searchActivities(any)).thenAnswer(
        (_) async => Result.ok(newResults),
      );

      final result = await useCase.execute(
        SearchFilters(cursor: 'cursor1'),
        existing,
      );

      expect(result.isOk, isTrue);
      expect(result.valueOrNull?.items.length, equals(2));
      expect(result.valueOrNull?.nextCursor, equals('cursor2'));
    });
  });
}
```

## Related

- [Entities](entities.md) - Domain objects used in use cases
- [Repositories](repositories.md) - Data access contracts
- [ViewModels](../viewmodels/README.md) - Consumers of use cases
