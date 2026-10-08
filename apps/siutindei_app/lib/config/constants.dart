/// Application constants for functional/business logic.
///
/// This file contains NON-DESIGN constants that define application behavior:
/// - Language codes and names (API parameters)
/// - Pricing types (business logic)
/// - Schedule types (business logic)
/// - Day of week mappings (data formatting)
///
/// ## Design vs Functionality
///
/// This file: FUNCTIONALITY (what the app does)
/// - Language options for API filters
/// - Age presets for quick selection
///
/// Theme files: DESIGN (how the app looks)
/// - Colors, spacing, typography
/// - Component styles
/// - Visual appearance
///
/// Keep these separated so design changes don't affect business logic.
library;

/// App-wide constants for filter options and data formatting.
class AppConstants {
  AppConstants._();

  // ============================================================
  // LANGUAGE OPTIONS
  // Used for activity language filtering
  // ============================================================

  /// Supported language codes and their display names.
  /// Keys are ISO 639-1 codes matching the API specification.
  static const Map<String, String> languageOptions = {
    'en': 'English',
    'zh': '中文',
    'ja': '日本語',
    'ko': '한국어',
    'fr': 'Français',
    'de': 'Deutsch',
    'es': 'Español',
    'pt': 'Português',
    'it': 'Italiano',
    'ru': 'Русский',
    'ar': 'العربية',
    'hi': 'हिन्दी',
    'th': 'ไทย',
    'vi': 'Tiếng Việt',
    'id': 'Bahasa Indonesia',
    'ms': 'Bahasa Melayu',
    'tl': 'Filipino',
    'nl': 'Nederlands',
    'pl': 'Polski',
    'tr': 'Türkçe',
    'yue': '廣東話',
  };

  // ============================================================
  // DAY OF WEEK
  // API uses 0=Sunday, 6=Saturday
  // ============================================================

  /// Full day names (0 = Sunday).
  static const List<String> daysOfWeek = [
    'Sunday',
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
  ];

  /// Short day names (0 = Sunday).
  static const List<String> daysOfWeekShort = [
    'Sun',
    'Mon',
    'Tue',
    'Wed',
    'Thu',
    'Fri',
    'Sat',
  ];

  // ============================================================
  // PRICING TYPES
  // Matches API pricing_type enum
  // ============================================================

  /// Pricing types with display names.
  static const Map<String, String> pricingTypes = {
    'per_class': 'Per Class',
    'per_sessions': 'Per Term',
    'per_hour': 'Hourly',
    'per_day': 'Daily',
    'free': 'Free',
  };

  // ============================================================
  // SCHEDULE TYPES
  // Matches API schedule_type enum
  // ============================================================

  /// Schedule types with display names.
  static const Map<String, String> scheduleTypes = {
    'weekly': 'Weekly',
    'monthly': 'Monthly',
    'date_specific': 'One-time',
  };

  // ============================================================
  // AGE PRESETS
  // Quick selection options for age filtering
  // ============================================================

  /// Age range presets for quick filtering.
  /// Key is display label, value is the age to filter by.
  static const Map<String, int> agePresets = {
    'Toddler (0-2)': 0,
    'Preschool (3-5)': 3,
    'Primary (6-12)': 6,
    'Teen (13-18)': 13,
  };

  // ============================================================
  // TIME UTILITIES
  // ============================================================

  /// Converts minutes from midnight to a readable time string.
  ///
  /// Example: 600 -> "10:00 AM"
  static String minutesToTimeString(int minutes) {
    final hours = minutes ~/ 60;
    final mins = minutes % 60;
    final period = hours >= 12 ? 'PM' : 'AM';
    final displayHours = hours == 0 ? 12 : (hours > 12 ? hours - 12 : hours);
    return '${displayHours.toString().padLeft(2, '0')}:'
        '${mins.toString().padLeft(2, '0')} $period';
  }

  /// Converts hour and minute to minutes from midnight.
  ///
  /// Example: (14, 30) -> 870
  static int timeOfDayToMinutes(int hour, int minute) {
    return hour * 60 + minute;
  }

  /// Gets the full day name from day of week index.
  static String getDayName(int dayOfWeek) {
    return daysOfWeek[dayOfWeek % 7];
  }

  /// Gets the short day name from day of week index.
  static String getDayNameShort(int dayOfWeek) {
    return daysOfWeekShort[dayOfWeek % 7];
  }

  /// Gets the display name for a language code.
  static String getLanguageName(String code) {
    return languageOptions[code] ?? code.toUpperCase();
  }

  /// Gets the display name for a pricing type.
  static String getPricingTypeName(String type) {
    return pricingTypes[type] ?? type;
  }

  /// Gets the display name for a schedule type.
  static String getScheduleTypeName(String type) {
    return scheduleTypes[type] ?? type;
  }
}
