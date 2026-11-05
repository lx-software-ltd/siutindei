# Domain Entities

Domain entities are pure business objects that represent core concepts in the application. They are framework-agnostic and contain only business logic.

## Overview

Entities in this app represent:
- Activities and their attributes
- Organizations that provide activities
- Locations where activities take place
- Pricing information
- Schedule details
- Search filters and results

## Location

```
lib/domain/entities/
├── entities.dart    # Barrel file
├── activity.dart    # Activity-related entities
└── search.dart      # Search-related entities
```

## Entity Design Principles

1. **Immutable**: All fields are final
2. **No Framework Dependencies**: Pure Dart, no Flutter imports
3. **Business Logic**: Contains domain-specific methods
4. **Value Equality**: Implements `==` and `hashCode`
5. **Type Safety**: Uses enums instead of strings for known values

## Activity Entities

### ActivityEntity

Represents an activity offered by an organization.

```dart
class ActivityEntity {
  const ActivityEntity({
    required this.id,
    required this.name,
    this.description,
    this.ageMin,
    this.ageMax,
  });

  final String id;
  final String name;
  final String? description;
  final int? ageMin;
  final int? ageMax;

  /// Returns formatted age range display string
  String? get ageRangeDisplay {
    if (ageMin == null && ageMax == null) return null;
    if (ageMin != null && ageMax != null) return '$ageMin-$ageMax years';
    if (ageMin != null) return '$ageMin+ years';
    return 'Up to $ageMax years';
  }
}
```

### OrganizationEntity

Represents an organization that offers activities.

```dart
class OrganizationEntity {
  const OrganizationEntity({
    required this.id,
    required this.name,
    this.description,
    this.mediaUrls = const [],
  });

  final String id;
  final String name;
  final String? description;
  final List<String> mediaUrls;

  /// Returns the primary media URL
  String? get primaryMediaUrl =>
      mediaUrls.isNotEmpty ? mediaUrls.first : null;
}
```

### LocationEntity

Represents a physical location.

```dart
class LocationEntity {
  const LocationEntity({
    required this.id,
    required this.district,
    this.address,
    this.latitude,
    this.longitude,
  });

  final String id;
  final String district;
  final String? address;
  final double? latitude;
  final double? longitude;

  /// Returns true if coordinates are available
  bool get hasCoordinates => latitude != null && longitude != null;
}
```

### PricingEntity

Represents pricing information with type-safe pricing types.

```dart
class PricingEntity {
  const PricingEntity({
    required this.type,
    required this.amount,
    required this.currency,
    this.sessionsCount,
    this.freeTrialClassOffered = false,
  });

  final PricingType type;
  final double amount;
  final String currency;
  final int? sessionsCount;
  final bool freeTrialClassOffered;

  bool get isFree => amount == 0;

  /// Returns formatted price string
  String get formattedPrice {
    if (isFree) return 'Free';
    final priceStr = '${amount.toStringAsFixed(0)} $currency';
    return switch (type) {
      PricingType.perClass => '$priceStr/class',
      PricingType.perSessions =>
        sessionsCount != null
            ? '$priceStr/$sessionsCount classes/term'
            : '$priceStr/term',
      PricingType.perHour => '$priceStr/hour',
      PricingType.perDay => '$priceStr/day',
      PricingType.free => 'Free',
    };
  }
}

enum PricingType {
  perClass,
  perSessions,
  perHour,
  perDay,
  free,
  perMonth,
  perYear;

  static PricingType fromString(String value) => switch (value) {
    'per_class' => PricingType.perClass,
    'per_sessions' => PricingType.perSessions,
    'per_hour' => PricingType.perHour,
    'per_day' => PricingType.perDay,
    'free' => PricingType.free,
    'per_month' => PricingType.perMonth,
    'per_year' => PricingType.perYear,
    _ => PricingType.perClass,
  };

  String toApiString() => switch (this) {
    PricingType.perClass => 'per_class',
    PricingType.perSessions => 'per_sessions',
    PricingType.perHour => 'per_hour',
    PricingType.perDay => 'per_day',
    PricingType.free => 'free',
    PricingType.perMonth => 'per_month',
    PricingType.perYear => 'per_year',
  };
}
```

### ScheduleEntity

Represents when an activity takes place.

```dart
class ScheduleEntity {
  const ScheduleEntity({
    required this.type,
    this.dayOfWeekUtc,
    this.dayOfMonth,
    this.startMinutesUtc,
    this.endMinutesUtc,
    this.startAtUtc,
    this.endAtUtc,
    this.languages = const [],
  });

  final ScheduleType type;
  final int? dayOfWeekUtc;
  final int? dayOfMonth;
  final int? startMinutesUtc;
  final int? endMinutesUtc;
  final DateTime? startAtUtc;
  final DateTime? endAtUtc;
  final List<String> languages;

  /// Returns formatted time string
  String? get formattedTime { ... }

  /// Returns day of week name
  String? get dayOfWeekName { ... }
}

enum ScheduleType {
  weekly,
  monthly,
  oneTime,
  flexible;
}
```

## Search Entities

### ActivitySearchResultEntity

Aggregates all related entities for a complete search result.

```dart
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

  /// Unique identifier (uses activity ID)
  String get id => activity.id;
}
```

### SearchResultsEntity

Represents a paginated search response.

```dart
class SearchResultsEntity {
  const SearchResultsEntity({
    required this.items,
    this.nextCursor,
  });

  final List<ActivitySearchResultEntity> items;
  final String? nextCursor;

  bool get hasMore => nextCursor != null;
  bool get isEmpty => items.isEmpty;
  int get count => items.length;

  static const SearchResultsEntity empty = SearchResultsEntity(items: []);
}
```

### SearchFilters

Value object for search filter configuration.

```dart
class SearchFilters {
  const SearchFilters({
    this.searchQuery,
    this.age,
    this.district,
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

  // ... fields ...

  /// Returns true if any filter is active
  bool get hasActiveFilters => ...;

  /// Returns the count of active filters
  int get activeFilterCount => ...;

  /// Creates a copy with given fields replaced
  SearchFilters copyWith({ ... });

  /// Returns copy without cursor (for new searches)
  SearchFilters withoutCursor() => copyWith(clearCursor: true);

  /// Clears all filters
  SearchFilters clear() => const SearchFilters();

  static const SearchFilters empty = SearchFilters();
}
```

## Usage Examples

### Creating Entities

```dart
final activity = ActivityEntity(
  id: '123',
  name: 'Swimming Lessons',
  description: 'Learn to swim!',
  ageMin: 5,
  ageMax: 12,
);

print(activity.ageRangeDisplay); // "5-12 years"
```

### Using Search Filters

```dart
// Create filters
var filters = SearchFilters(
  age: 8,
  district: 'Central',
  pricingType: PricingType.perDay,
);

// Update filters
filters = filters.copyWith(
  dayOfWeekUtc: 1, // Tuesday
);

// Check filter state
print(filters.hasActiveFilters); // true
print(filters.activeFilterCount); // 3

// Clear for new search
filters = filters.withoutCursor();
```

### Working with Results

```dart
final results = SearchResultsEntity(
  items: [...],
  nextCursor: 'abc123',
);

if (results.hasMore) {
  // Load more results
  final nextFilters = filters.copyWith(cursor: results.nextCursor);
}
```

## Testing Entities

```dart
test('ActivityEntity formats age range correctly', () {
  expect(
    ActivityEntity(id: '1', name: 'Test', ageMin: 5, ageMax: 10).ageRangeDisplay,
    equals('5-10 years'),
  );

  expect(
    ActivityEntity(id: '1', name: 'Test', ageMin: 5).ageRangeDisplay,
    equals('5+ years'),
  );

  expect(
    ActivityEntity(id: '1', name: 'Test', ageMax: 10).ageRangeDisplay,
    equals('Up to 10 years'),
  );
});

test('SearchFilters counts active filters', () {
  final filters = SearchFilters(
    age: 8,
    district: 'Central',
    priceMin: 0,
    priceMax: 100,
  );

  expect(filters.activeFilterCount, equals(3)); // age, district, price range
});
```

## Related

- [Repositories](repositories.md) - Using entities in data contracts
- [Use Cases](use_cases.md) - Business operations with entities
- [Mappers](../data/mappers.md) - Converting to/from data models
