import '../../domain/entities/entities.dart';
import '../../models/activity_models.dart';

/// Mappers for converting between data models and domain entities.
///
/// These mappers handle the translation between the API response models
/// and the domain entities used throughout the application.
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
      categoryId: model.categoryId,
    );
  }

  /// Converts an API Organization model to domain entity.
  static OrganizationEntity organizationToEntity(Organization model) {
    return OrganizationEntity(
      id: model.id,
      name: model.name,
      description: model.description,
      mediaUrls: model.mediaUrls,
      logoMediaUrl: model.logoMediaUrl,
    );
  }

  /// Converts an API Location model to domain entity.
  static LocationEntity locationToEntity(Location model) {
    return LocationEntity(
      id: model.id,
      areaId: model.areaId,
      regionAreaId: model.regionAreaId,
      address: model.address,
      latitude: model.lat,
      longitude: model.lng,
      status: model.status,
    );
  }

  /// Converts an API Pricing model to domain entity.
  static PricingEntity pricingToEntity(Pricing model) {
    return PricingEntity(
      type: PricingType.fromString(model.pricingType),
      amount: model.amount,
      currency: model.currency,
      sessionsCount: model.sessionsCount,
      freeTrialClassOffered: model.freeTrialClassOffered,
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
      pricing: model.pricing == null ? null : pricingToEntity(model.pricing!),
      schedule: model.schedule == null
          ? null
          : scheduleToEntity(model.schedule!),
    );
  }

  /// Converts an ActivitySearchResponse to domain entity.
  static SearchResultsEntity searchResponseToEntity(
    ActivitySearchResponse response,
  ) {
    return SearchResultsEntity(
      items: response.items.map(searchResultToEntity).toList(),
      nextCursor: response.nextCursor,
      areaScope: response.statesAreaScope ? response.areaScope : null,
      areaScopeStated: response.statesAreaScope,
    );
  }
}

/// Mapper for converting domain filters to API query parameters.
class SearchFiltersMapper {
  const SearchFiltersMapper._();

  /// Converts domain SearchFilters to ActivitySearchFilters model.
  static ActivitySearchFilters toModel(SearchFilters filters) {
    return ActivitySearchFilters(
      age: filters.age,
      areaId: filters.areaId,
      categoryIds: filters.categoryIds,
      pricingType: filters.pricingType?.toApiString(),
      priceMin: filters.priceMin,
      priceMax: filters.priceMax,
      scheduleType: filters.scheduleType?.toApiString(),
      dayOfWeekUtc: filters.dayOfWeekUtc,
      startMinutesUtc: filters.startMinutesUtc,
      endMinutesUtc: filters.endMinutesUtc,
      languages: filters.languages,
      cursor: filters.cursor,
      limit: filters.limit,
    );
  }
}
