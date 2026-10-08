import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/core.dart';
import '../data/providers.dart';
import '../domain/entities/entities.dart';
import '../domain/use_cases/use_cases.dart';

/// State for the activities search feature.
///
/// Immutable state object following Flutter architecture guidelines.
/// Contains all data needed to render the search UI.
@immutable
class ActivitiesState {
  const ActivitiesState({
    this.results = const SearchResultsEntity(items: []),
    this.filters = SearchFilters.empty,
    this.isLoading = false,
    this.isLoadingMore = false,
    this.errorMessage,
  });

  /// The current search results.
  final SearchResultsEntity results;

  /// The current search filters.
  final SearchFilters filters;

  /// Whether a search is in progress.
  final bool isLoading;

  /// Whether more results are being loaded.
  final bool isLoadingMore;

  /// Error message, if any.
  final String? errorMessage;

  /// Convenience getter for items.
  List<ActivitySearchResultEntity> get items => results.items;

  /// Whether there are more results to load.
  bool get hasMore => results.hasMore;

  /// Whether results are empty.
  bool get isEmpty => results.isEmpty && !isLoading;

  /// Whether we're in an error state.
  bool get hasError => errorMessage != null;

  /// Creates a copy with the given fields replaced.
  ActivitiesState copyWith({
    SearchResultsEntity? results,
    SearchFilters? filters,
    bool? isLoading,
    bool? isLoadingMore,
    String? errorMessage,
    bool clearError = false,
  }) {
    return ActivitiesState(
      results: results ?? this.results,
      filters: filters ?? this.filters,
      isLoading: isLoading ?? this.isLoading,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }

  /// Initial state.
  static const ActivitiesState initial = ActivitiesState();
}

/// ViewModel for the activities search feature.
///
/// Follows Flutter architecture guidelines:
/// - Uses use cases for business logic
/// - Uses Result type for error handling
/// - Maintains immutable state
/// - Separates concerns (no direct API calls)
///
/// See: https://docs.flutter.dev/app-architecture/guide
class ActivitiesViewModel extends Notifier<ActivitiesState> {
  late final SearchActivitiesUseCase _searchUseCase;
  late final LoadMoreActivitiesUseCase _loadMoreUseCase;

  @override
  ActivitiesState build() {
    _searchUseCase = ref.watch(searchActivitiesUseCaseProvider);
    _loadMoreUseCase = ref.watch(loadMoreActivitiesUseCaseProvider);
    return ActivitiesState.initial;
  }

  /// Performs a new search with the given filters.
  ///
  /// Clears existing results and starts a fresh search.
  Future<void> search(SearchFilters filters) async {
    // Clear cursor for new search
    final searchFilters = filters.withoutCursor();

    state = state.copyWith(
      filters: searchFilters,
      isLoading: true,
      clearError: true,
    );

    final result = await _searchUseCase.execute(searchFilters);

    switch (result) {
      case Ok(value: final data):
        state = state.copyWith(results: data, isLoading: false);
      case Error(error: final e):
        state = state.copyWith(isLoading: false, errorMessage: _formatError(e));
    }
  }

  /// Loads more results using the current cursor.
  ///
  /// Appends new results to existing ones.
  Future<void> loadMore() async {
    if (state.isLoadingMore || !state.hasMore) return;

    // Update filters with cursor
    final filtersWithCursor = state.filters.copyWith(
      cursor: state.results.nextCursor,
    );

    state = state.copyWith(isLoadingMore: true, clearError: true);

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

  /// Updates the search filters without performing a search.
  void updateFilters(SearchFilters filters) {
    state = state.copyWith(filters: filters);
  }

  /// Clears all filters and results.
  void clear() {
    state = ActivitiesState.initial;
  }

  /// Clears the error message.
  void clearError() {
    state = state.copyWith(clearError: true);
  }

  /// Retries the last search.
  Future<void> retry() async {
    await search(state.filters);
  }

  /// Formats an exception into a user-friendly message.
  ///
  /// Uses typed exceptions for specific error handling.
  String _formatError(Exception e) {
    // Use typed exceptions for specific messages
    if (e is AppException) {
      return e.displayMessage;
    }
    return 'An error occurred. Please try again.';
  }

  /// Returns true if the current error is retryable.
  bool get isErrorRetryable {
    // Check if we can determine retryability from error
    return state.hasError;
  }
}

/// Provider for the [ActivitiesViewModel].
///
/// Uses dependency injection for testability.
/// Override providers in tests to mock dependencies.
final activitiesViewModelProvider =
    NotifierProvider<ActivitiesViewModel, ActivitiesState>(
      ActivitiesViewModel.new,
    );

/// Selector for items only - minimizes rebuilds.
final activitiesItemsProvider = Provider<List<ActivitySearchResultEntity>>((
  ref,
) {
  return ref.watch(activitiesViewModelProvider.select((s) => s.items));
});

/// Selector for loading state only.
final activitiesIsLoadingProvider = Provider<bool>((ref) {
  return ref.watch(activitiesViewModelProvider.select((s) => s.isLoading));
});

/// Selector for error state only.
final activitiesErrorProvider = Provider<String?>((ref) {
  return ref.watch(activitiesViewModelProvider.select((s) => s.errorMessage));
});

/// Selector for has more state only.
final activitiesHasMoreProvider = Provider<bool>((ref) {
  return ref.watch(activitiesViewModelProvider.select((s) => s.hasMore));
});

/// Selector for filters only.
final activitiesFiltersProvider = Provider<SearchFilters>((ref) {
  return ref.watch(activitiesViewModelProvider.select((s) => s.filters));
});
