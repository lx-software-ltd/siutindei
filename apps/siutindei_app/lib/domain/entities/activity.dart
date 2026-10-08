/// Domain entity representing an activity.
///
/// This is a pure business object without any framework dependencies.
/// It represents the core concept of an activity in the domain.
class ActivityEntity {
  const ActivityEntity({
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

  /// Returns a display string for the age range.
  String? get ageRangeDisplay {
    if (ageMin == null && ageMax == null) return null;
    if (ageMin != null && ageMax != null) return '$ageMin-$ageMax years';
    if (ageMin != null) return '$ageMin+ years';
    return 'Up to $ageMax years';
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ActivityEntity &&
          other.id == id &&
          other.name == name &&
          other.description == description &&
          other.ageMin == ageMin &&
          other.ageMax == ageMax);

  @override
  int get hashCode => Object.hash(id, name, description, ageMin, ageMax);

  @override
  String toString() => 'ActivityEntity(id: $id, name: $name)';
}

/// Domain entity representing an organization.
class OrganizationEntity {
  const OrganizationEntity({
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

  /// Returns the logo URL or the first media URL when available.
  String? get primaryMediaUrl =>
      logoMediaUrl ?? (mediaUrls.isNotEmpty ? mediaUrls.first : null);

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is OrganizationEntity &&
          other.id == id &&
          other.name == name &&
          other.description == description);

  @override
  int get hashCode => Object.hash(id, name, description);

  @override
  String toString() => 'OrganizationEntity(id: $id, name: $name)';
}

/// Domain entity representing a location.
class LocationEntity {
  const LocationEntity({
    required this.id,
    required this.areaId,
    this.regionAreaId,
    this.address,
    this.latitude,
    this.longitude,
  });

  final String id;
  final String areaId;
  final String? regionAreaId;
  final String? address;
  final double? latitude;
  final double? longitude;

  /// Returns true if this location has coordinates.
  bool get hasCoordinates => latitude != null && longitude != null;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is LocationEntity &&
          other.id == id &&
          other.areaId == areaId &&
          other.address == address);

  @override
  int get hashCode => Object.hash(id, areaId, address);

  @override
  String toString() => 'LocationEntity(id: $id, areaId: $areaId)';
}

/// Domain entity representing pricing information.
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

  /// Returns true if this is free.
  bool get isFree => type == PricingType.free || amount == 0;

  /// Returns a formatted price string.
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

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is PricingEntity &&
          other.type == type &&
          other.amount == amount &&
          other.currency == currency);

  @override
  int get hashCode => Object.hash(type, amount, currency);
}

/// Pricing type enumeration.
///
/// Values must match the API enum: per_class, per_sessions, per_hour,
/// per_day, free
/// (defined in docs/api/search.yaml).
enum PricingType {
  perClass,
  perSessions,
  perHour,
  perDay,
  free;

  /// Creates from API string value.
  static PricingType fromString(String value) => switch (value) {
    'per_class' => PricingType.perClass,
    'per_sessions' => PricingType.perSessions,
    'per_hour' => PricingType.perHour,
    'per_day' => PricingType.perDay,
    'free' => PricingType.free,
    _ => PricingType.perClass,
  };

  /// Returns the API string value.
  String toApiString() => switch (this) {
    PricingType.perClass => 'per_class',
    PricingType.perSessions => 'per_sessions',
    PricingType.perHour => 'per_hour',
    PricingType.perDay => 'per_day',
    PricingType.free => 'free',
  };
}

/// Domain entity representing a schedule.
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

  /// Returns a formatted time string.
  String? get formattedTime {
    if (startMinutesUtc == null) return null;
    final startHour = startMinutesUtc! ~/ 60;
    final startMin = startMinutesUtc! % 60;
    final startStr =
        '${startHour.toString().padLeft(2, '0')}:'
        '${startMin.toString().padLeft(2, '0')}';

    if (endMinutesUtc == null) return startStr;
    final endHour = endMinutesUtc! ~/ 60;
    final endMin = endMinutesUtc! % 60;
    final endStr =
        '${endHour.toString().padLeft(2, '0')}:'
        '${endMin.toString().padLeft(2, '0')}';
    return '$startStr - $endStr';
  }

  /// Returns the day of week as a string.
  String? get dayOfWeekName {
    if (dayOfWeekUtc == null) return null;
    const days = [
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ];
    if (dayOfWeekUtc! >= 0 && dayOfWeekUtc! < 7) {
      return days[dayOfWeekUtc!];
    }
    return null;
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is ScheduleEntity &&
          other.type == type &&
          other.dayOfWeekUtc == dayOfWeekUtc &&
          other.startMinutesUtc == startMinutesUtc);

  @override
  int get hashCode => Object.hash(type, dayOfWeekUtc, startMinutesUtc);
}

/// Schedule type enumeration.
///
/// Values must match the API enum: weekly, monthly, date_specific
/// (defined in docs/api/search.yaml).
enum ScheduleType {
  weekly,
  monthly,
  dateSpecific;

  /// Creates from API string value.
  static ScheduleType fromString(String value) => switch (value) {
    'weekly' => ScheduleType.weekly,
    'monthly' => ScheduleType.monthly,
    'date_specific' => ScheduleType.dateSpecific,
    _ => ScheduleType.weekly,
  };

  /// Returns the API string value.
  String toApiString() => switch (this) {
    ScheduleType.weekly => 'weekly',
    ScheduleType.monthly => 'monthly',
    ScheduleType.dateSpecific => 'date_specific',
  };
}
