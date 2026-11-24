# Data Mappers

Mappers handle transformation between API data models and domain entities, providing a clean separation between external data formats and internal business objects.

## Overview

Mappers:
- Convert API responses to domain entities
- Convert domain objects to API request formats
- Handle data transformation logic
- Provide type safety at data boundaries

## Location

```
lib/data/mappers/
└── activity_mapper.dart
```

## ActivityMapper

Converts activity-related API models to domain entities.

```dart
class ActivityMapper {
  const ActivityMapper._();

  /// Converts an API Activity model to domain entity.
  static ActivityEntity toEntity(Activity model) {
    return ActivityEntity(
      id: model.id,
      name: model.name,
      description: model.description,
      ageMin: model.ageMin,
      ageMax: model.ageMax,
    );
  }

  /// Converts an API Organization model to domain entity.
  static OrganizationEntity organizationToEntity(Organization model) {
    return OrganizationEntity(
      id: model.id,
      name: model.name,
      description: model.description,
      mediaUrls: model.mediaUrls,
    );
  }

  /// Converts an API Location model to domain entity.
  static LocationEntity locationToEntity(Location model) {
    return LocationEntity(
      id: model.id,
      district: model.district,
      address: model.address,
      latitude: model.lat,
      longitude: model.lng,
    );
  }

  /// Converts an API Pricing model to domain entity.
  static PricingEntity pricingToEntity(Pricing model) {
    return PricingEntity(
      type: PricingType.fromString(model.pricingType),
      amount: model.amount,
      amountMax: model.amountMax,
      currency: model.currency,
      sessionsCount: model.sessionsCount,
    );
  }

  /// Converts an API Schedule model to domain entity.
  static ScheduleEntity scheduleToEntity(Schedule model) {
    return ScheduleEntity(
      type: ScheduleType.fromString(model.scheduleType),
      dayOfWeekUtc: model.dayOfWeekUtc,
      dayOfMonth: model.dayOfMonth,
      startMinutesUtc: model.startMinutesUtc,
      endMinutesUtc: model.endMinutesUtc,
      startAtUtc: model.startAtUtc != null
          ? DateTime.tryParse(model.startAtUtc!)
          : null,
      endAtUtc: model.endAtUtc != null
          ? DateTime.tryParse(model.endAtUtc!)
          : null,
      languages: model.languages,
    );
  }

  /// Converts a full ActivitySearchResult to domain entity.
  static ActivitySearchResultEntity searchResultToEntity(
    ActivitySearchResult model,
  ) {
    return ActivitySearchResultEntity(
      activity: toEntity(model.activity),
      organization: organizationToEntity(model.organization),
      location: locationToEntity(model.location),
      pricing: pricingToEntity(model.pricing),
      schedule: scheduleToEntity(model.schedule),
    );
  }

  /// Converts an ActivitySearchResponse to domain entity.
  static SearchResultsEntity searchResponseToEntity(
    ActivitySearchResponse response,
  ) {
    return SearchResultsEntity(
      items: response.items.map(searchResultToEntity).toList(),
      nextCursor: response.nextCursor,
    );
  }
}
```

## SearchFiltersMapper

Converts domain search filters to API query parameters.

```dart
class SearchFiltersMapper {
  const SearchFiltersMapper._();

  /// Converts domain SearchFilters to ActivitySearchFilters model.
  static ActivitySearchFilters toModel(SearchFilters filters) {
    return ActivitySearchFilters(
      searchQuery: filters.searchQuery,
      age: filters.age,
      district: filters.district,
      pricingType: filters.pricingType?.toApiString(),
      priceMin: filters.priceMin,
      priceMax: filters.priceMax,
      scheduleType: filters.scheduleType?.toApiString(),
      dayOfWeekUtc: filters.dayOfWeekUtc,
      dayOfMonth: filters.dayOfMonth,
      startMinutesUtc: filters.startMinutesUtc,
      endMinutesUtc: filters.endMinutesUtc,
      startAtUtc: filters.startAtUtc?.toIso8601String(),
      endAtUtc: filters.endAtUtc?.toIso8601String(),
      languages: filters.languages,
      cursor: filters.cursor,
      limit: filters.limit,
    );
  }
}
```

## Design Principles

### 1. Static Methods

Mappers use static methods for stateless transformation:

```dart
class MyMapper {
  const MyMapper._(); // Private constructor prevents instantiation

  static EntityType toEntity(ModelType model) { ... }
  static ModelType toModel(EntityType entity) { ... }
}
```

### 2. Pure Functions

Mapper methods should have no side effects:

```dart
// Good - pure function
static ActivityEntity toEntity(Activity model) {
  return ActivityEntity(
    id: model.id,
    name: model.name,
  );
}

// Bad - has side effects
static ActivityEntity toEntity(Activity model) {
  logger.info('Converting activity'); // Side effect
  return ActivityEntity(...);
}
```

### 3. Null Safety

Handle nullable fields explicitly:

```dart
static ScheduleEntity scheduleToEntity(Schedule model) {
  return ScheduleEntity(
    // Parse nullable DateTime
    startAtUtc: model.startAtUtc != null
        ? DateTime.tryParse(model.startAtUtc!)
        : null,
    // Default for nullable list
    languages: model.languages ?? const [],
  );
}
```

### 4. Type Conversion

Handle type differences between API and domain:

```dart
// API uses strings, domain uses enums
static PricingEntity pricingToEntity(Pricing model) {
  return PricingEntity(
    type: PricingType.fromString(model.pricingType), // String -> Enum
    amount: model.amount,
    amountMax: model.amountMax,
    currency: model.currency,
  );
}
```

## Mapping Direction

```
API Model ──► toEntity() ──► Domain Entity
     ▲                              │
     │                              │
     └───── toModel() ◄─────────────┘
```

### Model to Entity (API Response)

```dart
// Called when receiving API data
final entity = ActivityMapper.toEntity(apiModel);
```

### Entity to Model (API Request)

```dart
// Called when sending API request
final model = SearchFiltersMapper.toModel(domainFilters);
```

## Complex Mappings

### Nested Objects

```dart
static ActivitySearchResultEntity searchResultToEntity(
  ActivitySearchResult model,
) {
  return ActivitySearchResultEntity(
    activity: toEntity(model.activity),           // Nested mapping
    organization: organizationToEntity(model.organization),
    location: locationToEntity(model.location),
    pricing: pricingToEntity(model.pricing),
    schedule: scheduleToEntity(model.schedule),
  );
}
```

### Collections

```dart
static SearchResultsEntity searchResponseToEntity(
  ActivitySearchResponse response,
) {
  return SearchResultsEntity(
    items: response.items.map(searchResultToEntity).toList(), // Map collection
    nextCursor: response.nextCursor,
  );
}
```

### Conditional Mapping

```dart
static LocationEntity locationToEntity(Location model) {
  return LocationEntity(
    id: model.id,
    district: model.district,
    address: model.address,
    // Only include coordinates if both present
    latitude: model.lat != null && model.lng != null ? model.lat : null,
    longitude: model.lat != null && model.lng != null ? model.lng : null,
  );
}
```

## Testing Mappers

```dart
void main() {
  group('ActivityMapper', () {
    test('toEntity maps all fields correctly', () {
      final model = Activity(
        id: '123',
        name: 'Swimming',
        description: 'Learn to swim',
        ageMin: 5,
        ageMax: 12,
      );

      final entity = ActivityMapper.toEntity(model);

      expect(entity.id, equals('123'));
      expect(entity.name, equals('Swimming'));
      expect(entity.description, equals('Learn to swim'));
      expect(entity.ageMin, equals(5));
      expect(entity.ageMax, equals(12));
    });

    test('pricingToEntity converts pricing type correctly', () {
      final model = Pricing(
        pricingType: 'per_hour',
        amount: 100,
        currency: 'USD',
      );

      final entity = ActivityMapper.pricingToEntity(model);

      expect(entity.type, equals(PricingType.perHour));
    });

    test('scheduleToEntity parses DateTime correctly', () {
      final model = Schedule(
        scheduleType: 'weekly',
        startAtUtc: '2024-01-15T10:00:00Z',
        languages: ['en', 'es'],
      );

      final entity = ActivityMapper.scheduleToEntity(model);

      expect(entity.startAtUtc, isNotNull);
      expect(entity.startAtUtc?.year, equals(2024));
      expect(entity.languages, equals(['en', 'es']));
    });

    test('handles null optional fields', () {
      final model = Activity(
        id: '123',
        name: 'Swimming',
        description: null,
        ageMin: null,
        ageMax: null,
      );

      final entity = ActivityMapper.toEntity(model);

      expect(entity.description, isNull);
      expect(entity.ageMin, isNull);
      expect(entity.ageMax, isNull);
    });
  });

  group('SearchFiltersMapper', () {
    test('toModel converts all filter fields', () {
      final filters = SearchFilters(
        searchQuery: 'swimming',
        age: 8,
        pricingType: PricingType.perDay,
        dayOfWeekUtc: 1,
      );

      final model = SearchFiltersMapper.toModel(filters);

      expect(model.searchQuery, equals('swimming'));
      expect(model.age, equals(8));
      expect(model.pricingType, equals('per_day'));
      expect(model.dayOfWeekUtc, equals(1));
    });

    test('toModel handles DateTime conversion', () {
      final now = DateTime.now();
      final filters = SearchFilters(startAtUtc: now);

      final model = SearchFiltersMapper.toModel(filters);

      expect(model.startAtUtc, equals(now.toIso8601String()));
    });
  });
}
```

## Related

- [Data Repositories](repositories.md) - Use mappers for transformation
- [Domain Entities](../domain/entities.md) - Target of API-to-Entity mapping
