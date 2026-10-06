class ActivitySearchFilters {
  ActivitySearchFilters({
    this.age,
    this.areaId,
    this.categoryIds = const [],
    this.pricingType,
    this.priceMin,
    this.priceMax,
    this.scheduleType,
    this.dayOfWeekUtc,
    this.startMinutesUtc,
    this.endMinutesUtc,
    this.languages = const [],
    this.cursor,
    this.limit = 50,
  });

  final int? age;
  final String? areaId;
  final List<String> categoryIds;
  final String? pricingType;
  final double? priceMin;
  final double? priceMax;
  final String? scheduleType;
  final int? dayOfWeekUtc;
  final int? startMinutesUtc;
  final int? endMinutesUtc;
  final List<String> languages;
  final String? cursor;
  final int limit;

  /// Creates a copy of this filters with the given fields replaced.
  ActivitySearchFilters copyWith({
    int? age,
    String? areaId,
    List<String>? categoryIds,
    String? pricingType,
    double? priceMin,
    double? priceMax,
    String? scheduleType,
    int? dayOfWeekUtc,
    int? startMinutesUtc,
    int? endMinutesUtc,
    List<String>? languages,
    String? cursor,
    int? limit,
    bool clearAge = false,
    bool clearAreaId = false,
    bool clearPricingType = false,
    bool clearPriceMin = false,
    bool clearPriceMax = false,
    bool clearScheduleType = false,
    bool clearDayOfWeekUtc = false,
    bool clearStartMinutesUtc = false,
    bool clearEndMinutesUtc = false,
    bool clearCursor = false,
  }) {
    return ActivitySearchFilters(
      age: clearAge ? null : (age ?? this.age),
      areaId: clearAreaId ? null : (areaId ?? this.areaId),
      categoryIds: categoryIds ?? this.categoryIds,
      pricingType: clearPricingType ? null : (pricingType ?? this.pricingType),
      priceMin: clearPriceMin ? null : (priceMin ?? this.priceMin),
      priceMax: clearPriceMax ? null : (priceMax ?? this.priceMax),
      scheduleType:
          clearScheduleType ? null : (scheduleType ?? this.scheduleType),
      dayOfWeekUtc:
          clearDayOfWeekUtc ? null : (dayOfWeekUtc ?? this.dayOfWeekUtc),
      startMinutesUtc:
          clearStartMinutesUtc ? null : (startMinutesUtc ?? this.startMinutesUtc),
      endMinutesUtc:
          clearEndMinutesUtc ? null : (endMinutesUtc ?? this.endMinutesUtc),
      languages: languages ?? this.languages,
      cursor: clearCursor ? null : (cursor ?? this.cursor),
      limit: limit ?? this.limit,
    );
  }

  /// Returns true if any filter is active.
  bool get hasActiveFilters =>
      age != null ||
      areaId != null ||
      pricingType != null ||
      priceMin != null ||
      priceMax != null ||
      scheduleType != null ||
      dayOfWeekUtc != null ||
      startMinutesUtc != null ||
      endMinutesUtc != null ||
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
    if (startMinutesUtc != null || endMinutesUtc != null) count++;
    if (languages.isNotEmpty) count++;
    return count;
  }

  /// Creates a fresh filters instance with no cursor (for new searches).
  ActivitySearchFilters withoutCursor() => copyWith(clearCursor: true);

  Map<String, String> toQueryParameters() {
    final params = <String, String>{};
    void setParam(String key, Object? value) {
      if (value == null) {
        return;
      }
      params[key] = value.toString();
    }

    setParam('age', age);
    setParam('area_id', areaId);
    if (categoryIds.isNotEmpty) {
      params['category_id'] = categoryIds.join(',');
    }
    setParam('pricing_type', pricingType);
    setParam('price_min', priceMin);
    setParam('price_max', priceMax);
    setParam('schedule_type', scheduleType);
    setParam('day_of_week_utc', dayOfWeekUtc);
    setParam('start_minutes_utc', startMinutesUtc);
    setParam('end_minutes_utc', endMinutesUtc);
    if (languages.isNotEmpty) {
      params['language'] = languages.join(',');
    }
    setParam('cursor', cursor);
    setParam('limit', limit);
    return params;
  }

  @override
  String toString() {
    return 'ActivitySearchFilters(age: $age, areaId: $areaId, '
        'pricingType: $pricingType, languages: $languages)';
  }
}

class ActivitySearchResponse {
  ActivitySearchResponse({
    required this.items,
    required this.nextCursor,
    this.categoryMatch = 'exact',
  });

  final List<ActivitySearchResult> items;
  final String? nextCursor;
  final String categoryMatch;

  factory ActivitySearchResponse.fromJson(Map<String, dynamic> json) {
    final itemsJson = json['items'] as List<dynamic>? ?? [];
    return ActivitySearchResponse(
      items: itemsJson
          .map(
            (item) => ActivitySearchResult.fromJson(
              item as Map<String, dynamic>,
            ),
          )
          .toList(),
      nextCursor: json['next_cursor'] as String?,
      categoryMatch: json['category_match'] as String? ?? 'exact',
    );
  }
}

class ActivitySearchResult {
  ActivitySearchResult({
    required this.activity,
    required this.organization,
    required this.location,
    required this.pricing,
    required this.schedule,
  });

  final Activity activity;
  final Organization organization;
  final Location location;
  final Pricing pricing;
  final Schedule schedule;

  factory ActivitySearchResult.fromJson(Map<String, dynamic> json) {
    return ActivitySearchResult(
      activity: Activity.fromJson(json['activity'] as Map<String, dynamic>),
      organization: Organization.fromJson(json['organization'] as Map<String, dynamic>),
      location: Location.fromJson(json['location'] as Map<String, dynamic>),
      pricing: Pricing.fromJson(json['pricing'] as Map<String, dynamic>),
      schedule: Schedule.fromJson(json['schedule'] as Map<String, dynamic>),
    );
  }
}

class Activity {
  Activity({
    required this.id,
    required this.name,
    this.description,
    this.ageMin,
    this.ageMax,
    this.categoryId,
  });

  final String id;
  final String name;
  final String? description;
  final int? ageMin;
  final int? ageMax;
  final String? categoryId;

  factory Activity.fromJson(Map<String, dynamic> json) {
    return Activity(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      ageMin: json['age_min'] as int?,
      ageMax: json['age_max'] as int?,
      categoryId: json['category_id'] as String?,
    );
  }
}

class Organization {
  Organization({
    required this.id,
    required this.name,
    this.description,
    this.mediaUrls = const [],
    this.logoMediaUrl,
  });

  final String id;
  final String name;
  final String? description;
  final List<String> mediaUrls;
  final String? logoMediaUrl;

  factory Organization.fromJson(Map<String, dynamic> json) {
    final mediaUrlsJson = json['media_urls'] as List<dynamic>? ?? [];
    final logoMediaUrl = json['logo_media_url'] as String?;
    return Organization(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      mediaUrls: mediaUrlsJson.map((e) => e as String).toList(),
      logoMediaUrl: logoMediaUrl,
    );
  }

  /// Returns the logo URL or the first media URL when available.
  String? get primaryMediaUrl =>
      logoMediaUrl ?? (mediaUrls.isNotEmpty ? mediaUrls.first : null);
}

class Location {
  Location({
    required this.id,
    required this.areaId,
    this.regionAreaId,
    this.address,
    this.lat,
    this.lng,
  });

  final String id;
  final String areaId;
  final String? regionAreaId;
  final String? address;
  final double? lat;
  final double? lng;

  factory Location.fromJson(Map<String, dynamic> json) {
    return Location(
      id: json['id'] as String,
      areaId: json['area_id'] as String,
      regionAreaId: json['region_area_id'] as String?,
      address: json['address'] as String?,
      lat: (json['lat'] as num?)?.toDouble(),
      lng: (json['lng'] as num?)?.toDouble(),
    );
  }
}

class Pricing {
  Pricing({
    required this.pricingType,
    required this.amount,
    required this.currency,
    this.sessionsCount,
    this.freeTrialClassOffered = false,
  });

  final String pricingType;
  final double amount;
  final String currency;
  final int? sessionsCount;
  final bool freeTrialClassOffered;

  factory Pricing.fromJson(Map<String, dynamic> json) {
    return Pricing(
      pricingType: json['pricing_type'] as String,
      amount: (json['amount'] as num).toDouble(),
      currency: json['currency'] as String,
      sessionsCount: json['sessions_count'] as int?,
      freeTrialClassOffered:
          json['free_trial_class_offered'] as bool? ?? false,
    );
  }
}

class Schedule {
  Schedule({
    required this.scheduleType,
    this.dayOfWeekUtc,
    this.dayOfMonth,
    this.startMinutesUtc,
    this.endMinutesUtc,
    this.startAtUtc,
    this.endAtUtc,
    required this.languages,
  });

  final String scheduleType;
  final int? dayOfWeekUtc;
  final int? dayOfMonth;
  final int? startMinutesUtc;
  final int? endMinutesUtc;
  final String? startAtUtc;
  final String? endAtUtc;
  final List<String> languages;

  factory Schedule.fromJson(Map<String, dynamic> json) {
    final languagesJson = json['languages'] as List<dynamic>? ?? [];
    var dayOfWeekUtc = json['day_of_week_utc'] as int?;
    var startMinutesUtc = json['start_minutes_utc'] as int?;
    var endMinutesUtc = json['end_minutes_utc'] as int?;
    final weeklyEntries = json['weekly_entries'] as List<dynamic>? ?? [];
    if (weeklyEntries.isNotEmpty) {
      final first = weeklyEntries.first as Map<String, dynamic>;
      dayOfWeekUtc = first['day_of_week_utc'] as int?;
      startMinutesUtc = first['start_minutes_utc'] as int?;
      endMinutesUtc = first['end_minutes_utc'] as int?;
    }
    return Schedule(
      scheduleType: json['schedule_type'] as String,
      dayOfWeekUtc: dayOfWeekUtc,
      dayOfMonth: json['day_of_month'] as int?,
      startMinutesUtc: startMinutesUtc,
      endMinutesUtc: endMinutesUtc,
      startAtUtc: json['start_at_utc'] as String?,
      endAtUtc: json['end_at_utc'] as String?,
      languages: languagesJson.map((e) => e as String).toList(),
    );
  }
}
