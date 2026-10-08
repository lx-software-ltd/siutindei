import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/amplify_config.dart';
import '../models/activity_models.dart';

/// Loads and queries the staging activity search JSON fixture over HTTP.
class StagingSearchService {
  StagingSearchService._();

  static Map<String, dynamic>? _fixture;

  static Future<Map<String, dynamic>> _loadFixture() async {
    if (_fixture != null) {
      return _fixture!;
    }

    final url = AppAmplifyConfig.stagingSearchFixtureUrl.trim();
    if (url.isEmpty) {
      throw StateError(
        'STAGING_SEARCH_FIXTURE_URL is required when '
        'STAGING_SEARCH_DATA_ENABLED=true',
      );
    }

    final response = await http.get(
      Uri.parse(url),
      headers: const {'Accept': 'application/json'},
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw StateError(
        'Failed to load staging search fixture (${response.statusCode}) '
        'from $url',
      );
    }

    _fixture = jsonDecode(response.body) as Map<String, dynamic>;
    return _fixture!;
  }

  static Future<ActivitySearchResponse> searchActivities(
    ActivitySearchFilters filters,
  ) async {
    final fixture = await _loadFixture();
    final items = (fixture['items'] as List<dynamic>? ?? [])
        .cast<Map<String, dynamic>>();
    final areaDescendants =
        (fixture['meta'] as Map<String, dynamic>?)?['area_descendants']
            as Map<String, dynamic>? ??
        {};

    var matched = items.where(
      (item) => _matches(item, filters, areaDescendants),
    );
    final sorted = matched.toList()
      ..sort((left, right) {
        final leftSort = left['_sort'] as Map<String, dynamic>;
        final rightSort = right['_sort'] as Map<String, dynamic>;
        final dayCompare = (leftSort['day_of_week_utc'] as int).compareTo(
          rightSort['day_of_week_utc'] as int,
        );
        if (dayCompare != 0) {
          return dayCompare;
        }
        final startCompare = (leftSort['start_minutes_utc'] as int).compareTo(
          rightSort['start_minutes_utc'] as int,
        );
        if (startCompare != 0) {
          return startCompare;
        }
        return (leftSort['schedule_id'] as String).compareTo(
          rightSort['schedule_id'] as String,
        );
      });

    var startIndex = 0;
    if (filters.cursor != null && filters.cursor!.isNotEmpty) {
      final parsed = _decodeCursor(filters.cursor!);
      if (parsed != null) {
        startIndex = sorted.indexWhere((item) {
          final sort = item['_sort'] as Map<String, dynamic>;
          final key = (
            sort['day_of_week_utc'] as int,
            sort['start_minutes_utc'] as int,
            sort['schedule_id'] as String,
          );
          return _compareSortKey(key, parsed) > 0;
        });
        if (startIndex < 0) {
          startIndex = sorted.length;
        }
      }
    }

    final limit = filters.limit;
    final slice = sorted.skip(startIndex).take(limit + 1).toList();
    final hasMore = slice.length > limit;
    final page = slice.take(limit).toList();
    String? nextCursor;
    if (hasMore && page.isNotEmpty) {
      final lastSort = page.last['_sort'] as Map<String, dynamic>;
      nextCursor = _encodeCursor(
        dayOfWeekUtc: lastSort['day_of_week_utc'] as int,
        startMinutesUtc: lastSort['start_minutes_utc'] as int,
        scheduleId: lastSort['schedule_id'] as String,
      );
    }

    return ActivitySearchResponse(
      items: page
          .map(
            (item) => ActivitySearchResult.fromJson(_apiItemFromFixture(item)),
          )
          .toList(),
      nextCursor: nextCursor,
    );
  }

  static Map<String, dynamic> _apiItemFromFixture(Map<String, dynamic> item) {
    final schedule = Map<String, dynamic>.from(
      item['schedule'] as Map<String, dynamic>,
    );
    final entries = (schedule['weekly_entries'] as List<dynamic>? ?? []);
    if (entries.isNotEmpty) {
      final first = entries.first as Map<String, dynamic>;
      schedule['day_of_week_utc'] = first['day_of_week_utc'];
      schedule['start_minutes_utc'] = first['start_minutes_utc'];
      schedule['end_minutes_utc'] = first['end_minutes_utc'];
    }
    return {
      'activity': item['activity'],
      'organization': item['organization'],
      'location': item['location'],
      'pricing': item['pricing'],
      'schedule': schedule,
    };
  }

  static bool _matches(
    Map<String, dynamic> item,
    ActivitySearchFilters filters,
    Map<String, dynamic> areaDescendants,
  ) {
    final activity = item['activity'] as Map<String, dynamic>;
    final location = item['location'] as Map<String, dynamic>;

    if (filters.areaId != null && filters.areaId!.isNotEmpty) {
      final allowed =
          (areaDescendants[filters.areaId] as List<dynamic>?)
              ?.map((value) => value as String)
              .toList() ??
          [filters.areaId!];
      if (!allowed.contains(location['area_id'] as String?)) {
        return false;
      }
    }

    if (filters.age != null) {
      final ageMin = activity['age_min'] as int?;
      final ageMax = activity['age_max'] as int?;
      if (ageMin == null || ageMax == null) {
        return false;
      }
      if (filters.age! < ageMin || filters.age! > ageMax) {
        return false;
      }
    }

    if (filters.categoryIds.isNotEmpty) {
      final categoryId = activity['category_id'] as String?;
      if (categoryId == null || !filters.categoryIds.contains(categoryId)) {
        return false;
      }
    }

    return true;
  }

  static (int, int, String)? _decodeCursor(String cursor) {
    try {
      var normalized = cursor.replaceAll('-', '+').replaceAll('_', '/');
      final padding = '=' * ((4 - normalized.length % 4) % 4);
      final decoded = utf8.decode(base64.decode(normalized + padding));
      final payload = jsonDecode(decoded) as Map<String, dynamic>;
      final scheduleId = payload['schedule_id'] as String?;
      final day = payload['day_of_week_utc'] as int?;
      final start = payload['start_minutes_utc'] as int?;
      if (scheduleId == null || day == null || start == null) {
        return null;
      }
      return (day, start, scheduleId);
    } on FormatException {
      return null;
    }
  }

  static String _encodeCursor({
    required int dayOfWeekUtc,
    required int startMinutesUtc,
    required String scheduleId,
  }) {
    final payload = jsonEncode({
      'schedule_id': scheduleId,
      'day_of_week_utc': dayOfWeekUtc,
      'start_minutes_utc': startMinutesUtc,
    });
    return base64Url.encode(utf8.encode(payload)).replaceAll('=', '');
  }

  static int _compareSortKey(
    (int, int, String) left,
    (int, int, String) right,
  ) {
    if (left.$1 != right.$1) {
      return left.$1.compareTo(right.$1);
    }
    if (left.$2 != right.$2) {
      return left.$2.compareTo(right.$2);
    }
    return left.$3.compareTo(right.$3);
  }
}
