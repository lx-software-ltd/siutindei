import 'activity.dart';

/// Domain entity representing an activity search result.
///
/// Aggregates all related entities for a complete search result.
class ActivitySearchResultEntity {
  const ActivitySearchResultEntity({
    required this.activity,
    required this.organization,
    required this.location,
    required this.pricing,
    required this.schedule,
  });

  final ActivityEntity activity;
  final OrganizationEntity organization;
  final LocationEntity location;
  final PricingEntity pricing;
  final ScheduleEntity schedule;

  /// Unique identifier for this search result (uses activity ID).
  String get id => activity.id;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ActivitySearchResultEntity &&
          other.activity == activity &&
          other.organization == organization);

  @override
  int get hashCode => Object.hash(activity, organization);
}

/// Domain entity representing a paginated search response.
class SearchResultsEntity {
  const SearchResultsEntity({required this.items, this.nextCursor});

  final List<ActivitySearchResultEntity> items;
  final String? nextCursor;

  /// Returns true if there are more results to load.
  bool get hasMore => nextCursor != null;

  /// Returns true if the results are empty.
  bool get isEmpty => items.isEmpty;

  /// Returns the count of items.
  int get count => items.length;

  /// Creates an empty result.
  static const SearchResultsEntity empty = SearchResultsEntity(items: []);
}

/// Value object for search filters.
///
/// Immutable filter configuration for activity search.
class SearchFilters {
  const SearchFilters({
    this.searchQuery,
    this.age,
    this.areaId,
    this.categoryIds = const [],
    this.pricingType,
    this.priceMin,
    this.priceMax,
    this.scheduleType,
    this.dayOfWeekUtc,
    this.dayOfMonth,
    this.startMinutesUtc,
    this.endMinutesUtc,
    this.startAtUtc,
    this.endAtUtc,
    this.languages = const [],
    this.cursor,
    this.limit = 50,
  });

  final String? searchQuery;
  final int? age;
  final String? areaId;
  final List<String> categoryIds;
  final PricingType? pricingType;
  final double? priceMin;
  final double? priceMax;
  final ScheduleType? scheduleType;
  final int? dayOfWeekUtc;
  final int? dayOfMonth;
  final int? startMinutesUtc;
  final int? endMinutesUtc;
  final DateTime? startAtUtc;
  final DateTime? endAtUtc;
  final List<String> languages;
  final String? cursor;
  final int limit;

  /// Returns true if any filter is active.
  bool get hasActiveFilters =>
      age != null ||
      areaId != null ||
      categoryIds.isNotEmpty ||
      pricingType != null ||
      priceMin != null ||
      priceMax != null ||
      scheduleType != null ||
      dayOfWeekUtc != null ||
      dayOfMonth != null ||
      startMinutesUtc != null ||
      endMinutesUtc != null ||
      startAtUtc != null ||
      endAtUtc != null ||
      languages.isNotEmpty;

  /// Returns the number of active filters.
  int get activeFilterCount {
    int count = 0;
    if (age != null) count++;
    if (areaId != null) count++;
    if (pricingType != null) count++;
    if (priceMin != null || priceMax != null) count++;
    if (scheduleType != null) count++;
    if (dayOfWeekUtc != null) count++;
    if (dayOfMonth != null) count++;
    if (startMinutesUtc != null || endMinutesUtc != null) count++;
    if (languages.isNotEmpty) count++;
    return count;
  }

  /// Creates a copy with the given fields replaced.
  SearchFilters copyWith({
    String? searchQuery,
    int? age,
    String? areaId,
    List<String>? categoryIds,
    PricingType? pricingType,
    double? priceMin,
    double? priceMax,
    ScheduleType? scheduleType,
    int? dayOfWeekUtc,
    int? dayOfMonth,
    int? startMinutesUtc,
    int? endMinutesUtc,
    DateTime? startAtUtc,
    DateTime? endAtUtc,
    List<String>? languages,
    String? cursor,
    int? limit,
    bool clearSearchQuery = false,
    bool clearAge = false,
    bool clearAreaId = false,
    bool clearPricingType = false,
    bool clearPriceMin = false,
    bool clearPriceMax = false,
    bool clearScheduleType = false,
    bool clearDayOfWeekUtc = false,
    bool clearDayOfMonth = false,
    bool clearStartMinutesUtc = false,
    bool clearEndMinutesUtc = false,
    bool clearStartAtUtc = false,
    bool clearEndAtUtc = false,
    bool clearCursor = false,
  }) {
    return SearchFilters(
      searchQuery: clearSearchQuery ? null : (searchQuery ?? this.searchQuery),
      age: clearAge ? null : (age ?? this.age),
      areaId: clearAreaId ? null : (areaId ?? this.areaId),
      categoryIds: categoryIds ?? this.categoryIds,
      pricingType: clearPricingType ? null : (pricingType ?? this.pricingType),
      priceMin: clearPriceMin ? null : (priceMin ?? this.priceMin),
      priceMax: clearPriceMax ? null : (priceMax ?? this.priceMax),
      scheduleType: clearScheduleType
          ? null
          : (scheduleType ?? this.scheduleType),
      dayOfWeekUtc: clearDayOfWeekUtc
          ? null
          : (dayOfWeekUtc ?? this.dayOfWeekUtc),
      dayOfMonth: clearDayOfMonth ? null : (dayOfMonth ?? this.dayOfMonth),
      startMinutesUtc: clearStartMinutesUtc
          ? null
          : (startMinutesUtc ?? this.startMinutesUtc),
      endMinutesUtc: clearEndMinutesUtc
          ? null
          : (endMinutesUtc ?? this.endMinutesUtc),
      startAtUtc: clearStartAtUtc ? null : (startAtUtc ?? this.startAtUtc),
      endAtUtc: clearEndAtUtc ? null : (endAtUtc ?? this.endAtUtc),
      languages: languages ?? this.languages,
      cursor: clearCursor ? null : (cursor ?? this.cursor),
      limit: limit ?? this.limit,
    );
  }

  /// Returns a copy with no cursor (for new searches).
  SearchFilters withoutCursor() => copyWith(clearCursor: true);

  /// Clears all filters.
  SearchFilters clear() => const SearchFilters();

  /// Default empty filters.
  static const SearchFilters empty = SearchFilters();

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SearchFilters &&
          other.searchQuery == searchQuery &&
          other.age == age &&
          other.areaId == areaId &&
          other.pricingType == pricingType &&
          other.priceMin == priceMin &&
          other.priceMax == priceMax &&
          other.scheduleType == scheduleType &&
          other.cursor == cursor &&
          other.limit == limit);

  @override
  int get hashCode => Object.hash(
    searchQuery,
    age,
    areaId,
    pricingType,
    priceMin,
    priceMax,
    scheduleType,
    cursor,
    limit,
  );
}
