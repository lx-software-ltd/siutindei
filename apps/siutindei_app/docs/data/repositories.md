# Data Layer Repositories

Repository implementations handle actual data access, including API calls, caching, and data transformation.

## Overview

Data repositories:
- Implement domain repository interfaces
- Handle API communication
- Transform data models to domain entities
- Manage caching (if applicable)
- Handle errors and wrap in `Result<T>`

## Location

```
lib/data/
├── data.dart                          # Barrel file
├── providers.dart                     # Dependency injection
├── repositories/
│   └── activity_repository_impl.dart  # Repository implementations
└── mappers/
    └── activity_mapper.dart           # Data transformation
```

## ActivityRepositoryImpl

Implements `ActivityRepository` using the API service.

```dart
class ActivityRepositoryImpl implements ActivityRepository {
  const ActivityRepositoryImpl(this._apiService);

  final ApiService _apiService;

  @override
  Future<Result<SearchResultsEntity>> searchActivities(
    SearchFilters filters,
  ) async {
    try {
      // Convert domain filters to API model
      final apiFilters = SearchFiltersMapper.toModel(filters);

      // Make API call
      final response = await _apiService.searchActivities(apiFilters);

      // Convert response to domain entity
      final results = ActivityMapper.searchResponseToEntity(response);

      return Result.ok(results);
    } on Exception catch (e) {
      return Result.error(e);
    }
  }

  @override
  Future<Result<ActivitySearchResultEntity>> getActivity(
    String activityId,
  ) async {
    // Implementation for single activity fetch
    return Result.error(
      UnimplementedError('Single activity endpoint not yet implemented'),
    );
  }
}
```

## OrganizationRepositoryImpl

Implements `OrganizationRepository`.

```dart
class OrganizationRepositoryImpl implements OrganizationRepository {
  const OrganizationRepositoryImpl(this._apiService);

  final ApiService _apiService;

  @override
  Future<Result<OrganizationEntity>> getOrganization(
    String organizationId,
  ) async {
    try {
      final response = await _apiService.getOrganization(organizationId);
      return Result.ok(ActivityMapper.organizationToEntity(response));
    } on Exception catch (e) {
      return Result.error(e);
    }
  }

  @override
  Future<Result<List<ActivitySearchResultEntity>>> getOrganizationActivities(
    String organizationId,
  ) async {
    try {
      final response = await _apiService.getOrgActivities(organizationId);
      final entities = response.map(ActivityMapper.searchResultToEntity).toList();
      return Result.ok(entities);
    } on Exception catch (e) {
      return Result.error(e);
    }
  }
}
```

## Dependency Injection

Repositories are provided through Riverpod:

```dart
/// Provider for [ActivityRepository].
final activityRepositoryProvider = Provider<ActivityRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return ActivityRepositoryImpl(apiService);
});

/// Provider for [OrganizationRepository].
final organizationRepositoryProvider = Provider<OrganizationRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return OrganizationRepositoryImpl(apiService);
});
```

## Error Handling

Repositories catch exceptions and return `Result.error`:

```dart
@override
Future<Result<SearchResultsEntity>> searchActivities(
  SearchFilters filters,
) async {
  try {
    final response = await _apiService.searchActivities(
      SearchFiltersMapper.toModel(filters),
    );
    return Result.ok(ActivityMapper.searchResponseToEntity(response));
  } on SocketException catch (e) {
    // Network error
    return Result.error(
      NetworkException('No internet connection: ${e.message}'),
    );
  } on TimeoutException catch (e) {
    // Timeout
    return Result.error(
      NetworkException('Request timed out: ${e.message}'),
    );
  } on FormatException catch (e) {
    // Invalid response format
    return Result.error(
      DataException('Invalid response format: ${e.message}'),
    );
  } on Exception catch (e) {
    // Generic error
    return Result.error(e);
  }
}
```

## Caching Pattern

Example of repository with caching:

```dart
class CachedActivityRepository implements ActivityRepository {
  CachedActivityRepository(this._apiService, this._cache);

  final ApiService _apiService;
  final Cache _cache;

  static const _cacheKey = 'search';
  static const _cacheDuration = Duration(minutes: 5);

  @override
  Future<Result<SearchResultsEntity>> searchActivities(
    SearchFilters filters,
  ) async {
    // Generate cache key from filters
    final key = '${_cacheKey}_${filters.hashCode}';

    // Check cache first
    final cached = await _cache.get<SearchResultsEntity>(key);
    if (cached != null) {
      return Result.ok(cached);
    }

    // Fetch from API
    try {
      final response = await _apiService.searchActivities(
        SearchFiltersMapper.toModel(filters),
      );
      final results = ActivityMapper.searchResponseToEntity(response);

      // Cache the result
      await _cache.set(key, results, _cacheDuration);

      return Result.ok(results);
    } on Exception catch (e) {
      return Result.error(e);
    }
  }
}
```

## Implementation Guidelines

### 1. Constructor Injection

```dart
class MyRepositoryImpl implements MyRepository {
  const MyRepositoryImpl(this._service1, this._service2);

  final Service1 _service1;
  final Service2 _service2;
}
```

### 2. Single Responsibility

Each repository should handle one aggregate root:

```dart
// Good - focused on activities
class ActivityRepositoryImpl implements ActivityRepository { ... }

// Good - focused on organizations
class OrganizationRepositoryImpl implements OrganizationRepository { ... }

// Bad - handles too much
class DataRepository implements ActivityRepository, OrganizationRepository { ... }
```

### 3. Use Mappers

Don't transform data inline; use dedicated mappers:

```dart
// Good - uses mapper
final entity = ActivityMapper.searchResponseToEntity(response);

// Bad - transforms inline
final entity = SearchResultsEntity(
  items: response.items.map((i) => ActivitySearchResultEntity(
    activity: ActivityEntity(id: i.activity.id, ...),
    // ... more inline transformation
  )).toList(),
);
```

### 4. Wrap All External Calls

Every external call should be in a try-catch:

```dart
@override
Future<Result<T>> operation() async {
  try {
    final response = await _externalService.call();
    return Result.ok(Mapper.toEntity(response));
  } on Exception catch (e) {
    return Result.error(e);
  }
}
```

## Testing Repositories

```dart
void main() {
  group('ActivityRepositoryImpl', () {
    late MockApiService mockApiService;
    late ActivityRepositoryImpl repository;

    setUp(() {
      mockApiService = MockApiService();
      repository = ActivityRepositoryImpl(mockApiService);
    });

    test('searchActivities returns mapped results on success', () async {
      final apiResponse = ActivitySearchResponse(
        items: [mockActivityResult],
        nextCursor: 'cursor123',
      );

      when(mockApiService.searchActivities(any)).thenAnswer(
        (_) async => apiResponse,
      );

      final result = await repository.searchActivities(SearchFilters());

      expect(result.isOk, isTrue);
      expect(result.valueOrNull?.items.length, equals(1));
      expect(result.valueOrNull?.nextCursor, equals('cursor123'));
    });

    test('searchActivities returns error on API failure', () async {
      when(mockApiService.searchActivities(any)).thenThrow(
        SocketException('Network error'),
      );

      final result = await repository.searchActivities(SearchFilters());

      expect(result.isError, isTrue);
      expect(result.errorOrNull, isA<SocketException>());
    });

    test('searchActivities converts filters correctly', () async {
      when(mockApiService.searchActivities(any)).thenAnswer(
        (_) async => ActivitySearchResponse(items: [], nextCursor: null),
      );

      await repository.searchActivities(
        SearchFilters(age: 8, district: 'Central'),
      );

      final captured = verify(
        mockApiService.searchActivities(captureAny),
      ).captured.single as ActivitySearchFilters;

      expect(captured.age, equals(8));
      expect(captured.district, equals('Central'));
    });
  });
}
```

## Related

- [Repository Interfaces](../domain/repositories.md) - Contracts implemented here
- [Mappers](mappers.md) - Data transformation utilities
