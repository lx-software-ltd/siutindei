import '../../core/exceptions/app_exceptions.dart';
import '../../core/utils/result.dart';
import '../entities/entities.dart';
import '../repositories/repositories.dart';

/// Use case for searching activities.
///
/// Encapsulates the business logic for activity search, including
/// validation and any domain-specific rules.
///
/// ## Usage
///
/// ```dart
/// final useCase = SearchActivitiesUseCase(repository);
/// final result = await useCase.execute(filters);
/// ```
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
      return ValidationException.outOfRange('Age', min: 0, max: 100);
    }

    // Price validation
    if (filters.priceMin != null && filters.priceMin! < 0) {
      return ValidationException.field('Minimum price', 'cannot be negative');
    }
    if (filters.priceMax != null && filters.priceMax! < 0) {
      return ValidationException.field('Maximum price', 'cannot be negative');
    }
    if (filters.priceMin != null &&
        filters.priceMax != null &&
        filters.priceMin! > filters.priceMax!) {
      return ValidationException.field(
        'Price range',
        'minimum cannot exceed maximum',
      );
    }

    // Time validation
    if (filters.startMinutesUtc != null &&
        (filters.startMinutesUtc! < 0 || filters.startMinutesUtc! > 1440)) {
      return ValidationException.outOfRange('Start time', min: 0, max: 1440);
    }
    if (filters.endMinutesUtc != null &&
        (filters.endMinutesUtc! < 0 || filters.endMinutesUtc! > 1440)) {
      return ValidationException.outOfRange('End time', min: 0, max: 1440);
    }

    // Day of week validation
    if (filters.dayOfWeekUtc != null &&
        (filters.dayOfWeekUtc! < 0 || filters.dayOfWeekUtc! > 6)) {
      return ValidationException.outOfRange('Day of week', min: 0, max: 6);
    }

    // Day of month validation
    if (filters.dayOfMonth != null &&
        (filters.dayOfMonth! < 1 || filters.dayOfMonth! > 31)) {
      return ValidationException.outOfRange('Day of month', min: 1, max: 31);
    }

    // Limit validation
    if (filters.limit < 1 || filters.limit > 100) {
      return ValidationException.outOfRange('Limit', min: 1, max: 100);
    }

    return null;
  }
}

/// Use case for loading more search results (pagination).
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
      return Result.error(InvalidStateException.noMoreItems());
    }

    final result = await _repository.searchActivities(currentFilters);

    return result.map(
      (newResults) => SearchResultsEntity(
        items: [...existingResults.items, ...newResults.items],
        nextCursor: newResults.nextCursor,
      ),
    );
  }
}
