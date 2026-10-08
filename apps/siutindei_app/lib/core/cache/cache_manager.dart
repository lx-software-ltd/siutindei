import 'dart:async';

import '../utils/result.dart';

/// Cache entry with value and metadata.
class CacheEntry<T> {
  const CacheEntry({
    required this.value,
    required this.cachedAt,
    this.expiresAt,
  });

  final T value;
  final DateTime cachedAt;
  final DateTime? expiresAt;

  /// Whether this entry has expired.
  bool get isExpired {
    if (expiresAt == null) return false;
    return DateTime.now().isAfter(expiresAt!);
  }

  /// Age of this entry.
  Duration get age => DateTime.now().difference(cachedAt);
}

/// Cache policy configuration.
class CachePolicy {
  const CachePolicy({
    this.maxAge = const Duration(minutes: 5),
    this.staleWhileRevalidate = true,
    this.persistToDisk = false,
  });

  /// Maximum age before cache is considered stale.
  final Duration maxAge;

  /// Whether to return stale data while fetching fresh data.
  final bool staleWhileRevalidate;

  /// Whether to persist cache to disk.
  final bool persistToDisk;

  /// Default policy for API responses.
  static const api = CachePolicy(
    maxAge: Duration(minutes: 5),
    staleWhileRevalidate: true,
  );

  /// Policy for rarely changing data.
  static const longLived = CachePolicy(
    maxAge: Duration(hours: 1),
    staleWhileRevalidate: true,
  );

  /// No caching.
  static const none = CachePolicy(
    maxAge: Duration.zero,
    staleWhileRevalidate: false,
  );
}

/// In-memory cache manager following offline-first pattern.
///
/// Implements the recommended caching strategy from Flutter architecture:
/// - Cache as single source of truth for data
/// - Stale-while-revalidate pattern
/// - Configurable cache policies
///
/// See: https://docs.flutter.dev/app-architecture/recommendations
class CacheManager {
  CacheManager._();

  static final CacheManager instance = CacheManager._();

  final Map<String, CacheEntry<dynamic>> _cache = {};
  final Map<String, Completer<dynamic>> _pendingFetches = {};

  /// Gets a cached value, or fetches it if not available.
  ///
  /// [key] - Unique cache key
  /// [fetch] - Function to fetch fresh data
  /// [policy] - Cache policy to apply
  ///
  /// Returns cached data immediately if available and not expired.
  /// If staleWhileRevalidate is true and data is stale, returns stale data
  /// and triggers background refresh.
  Future<Result<T>> getOrFetch<T>({
    required String key,
    required Future<Result<T>> Function() fetch,
    CachePolicy policy = CachePolicy.api,
  }) async {
    // Check cache first
    final cached = _cache[key] as CacheEntry<T>?;

    if (cached != null) {
      if (!cached.isExpired) {
        // Fresh cache hit
        return Result.ok(cached.value);
      }

      if (policy.staleWhileRevalidate) {
        // Return stale data and refresh in background
        _refreshInBackground(key, fetch, policy);
        return Result.ok(cached.value);
      }
    }

    // Cache miss or expired without stale-while-revalidate
    return _fetchAndCache(key, fetch, policy);
  }

  /// Gets cached value without fetching.
  T? get<T>(String key) {
    final entry = _cache[key] as CacheEntry<T>?;
    if (entry == null || entry.isExpired) return null;
    return entry.value;
  }

  /// Sets a cache value.
  void set<T>(String key, T value, {CachePolicy policy = CachePolicy.api}) {
    _cache[key] = CacheEntry<T>(
      value: value,
      cachedAt: DateTime.now(),
      expiresAt: policy.maxAge.inSeconds > 0
          ? DateTime.now().add(policy.maxAge)
          : null,
    );
  }

  /// Invalidates a specific cache key.
  void invalidate(String key) {
    _cache.remove(key);
  }

  /// Invalidates all cache entries matching a prefix.
  void invalidatePrefix(String prefix) {
    _cache.removeWhere((key, _) => key.startsWith(prefix));
  }

  /// Clears all cache.
  void clear() {
    _cache.clear();
  }

  /// Gets cache statistics.
  CacheStats get stats => CacheStats(
    entryCount: _cache.length,
    pendingFetches: _pendingFetches.length,
  );

  Future<Result<T>> _fetchAndCache<T>(
    String key,
    Future<Result<T>> Function() fetch,
    CachePolicy policy,
  ) async {
    // Deduplicate concurrent fetches for same key
    if (_pendingFetches.containsKey(key)) {
      return (await _pendingFetches[key]!.future) as Result<T>;
    }

    final completer = Completer<Result<T>>();
    _pendingFetches[key] = completer;

    try {
      final result = await fetch();

      if (result case Ok(value: final data)) {
        set(key, data, policy: policy);
      }

      completer.complete(result);
      return result;
    } catch (e) {
      final error = Result<T>.error(
        e is Exception ? e : Exception(e.toString()),
      );
      completer.complete(error);
      return error;
    } finally {
      _pendingFetches.remove(key);
    }
  }

  void _refreshInBackground<T>(
    String key,
    Future<Result<T>> Function() fetch,
    CachePolicy policy,
  ) {
    // Don't await - run in background
    Future(() async {
      final result = await fetch();
      if (result case Ok(value: final data)) {
        set(key, data, policy: policy);
      }
    });
  }
}

/// Cache statistics.
class CacheStats {
  const CacheStats({required this.entryCount, required this.pendingFetches});

  final int entryCount;
  final int pendingFetches;
}

/// Cache key builder for consistent key generation.
class CacheKeys {
  CacheKeys._();

  /// Search results cache key.
  static String searchResults(String filtersHash) =>
      'search_results_$filtersHash';

  /// Activity detail cache key.
  static String activityDetail(String activityId) =>
      'activity_detail_$activityId';

  /// Organization cache key.
  static String organization(String orgId) => 'organization_$orgId';

  /// Organization activities cache key.
  static String organizationActivities(String orgId) => 'org_activities_$orgId';
}
