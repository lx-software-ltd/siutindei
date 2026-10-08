import 'dart:io';

import '../../core/cache/cache_manager.dart';
import '../../core/exceptions/app_exceptions.dart';
import '../../core/utils/result.dart';
import '../../domain/entities/entities.dart';
import '../../domain/repositories/repositories.dart';
import '../../services/api_service.dart';
import '../mappers/activity_mapper.dart';

/// Implementation of [ActivityRepository] using the API service.
///
/// Follows Flutter architecture recommendations:
/// - Repository as single source of truth for activity data
/// - Caching layer for offline-first support
/// - Proper error handling with typed exceptions
///
/// See: https://docs.flutter.dev/app-architecture/recommendations
class ActivityRepositoryImpl implements ActivityRepository {
  ActivityRepositoryImpl(this._apiService, {CacheManager? cacheManager})
    : _cache = cacheManager ?? CacheManager.instance;

  final ApiService _apiService;
  final CacheManager _cache;

  @override
  Future<Result<SearchResultsEntity>> searchActivities(
    SearchFilters filters,
  ) async {
    // Generate cache key from filters
    final cacheKey = CacheKeys.searchResults(filters.hashCode.toString());

    // Use cache with stale-while-revalidate for better UX
    return _cache.getOrFetch<SearchResultsEntity>(
      key: cacheKey,
      policy: CachePolicy.api,
      fetch: () => _fetchSearchResults(filters),
    );
  }

  /// Fetches search results from API.
  Future<Result<SearchResultsEntity>> _fetchSearchResults(
    SearchFilters filters,
  ) async {
    try {
      // Convert domain filters to API model
      final apiFilters = SearchFiltersMapper.toModel(filters);

      // Make API call
      final response = await _apiService.searchActivities(apiFilters);

      // Convert response to domain entity
      final results = ActivityMapper.searchResponseToEntity(response);

      return Result.ok(results);
    } on SocketException catch (e) {
      return Result.error(NetworkException.fromError(e));
    } on HttpException {
      return Result.error(NetworkException.serverError());
    } on FormatException catch (e) {
      return Result.error(DataException.invalidFormat(e.message));
    } on Exception catch (e) {
      return Result.error(NetworkException.fromError(e));
    }
  }

  @override
  Future<Result<ActivitySearchResultEntity>> getActivity(
    String activityId,
  ) async {
    final cacheKey = CacheKeys.activityDetail(activityId);

    return _cache.getOrFetch<ActivitySearchResultEntity>(
      key: cacheKey,
      policy: CachePolicy.longLived,
      fetch: () => _fetchActivity(activityId),
    );
  }

  Future<Result<ActivitySearchResultEntity>> _fetchActivity(
    String activityId,
  ) async {
    // For now, we don't have a dedicated endpoint for single activity
    // This would typically call a specific API endpoint
    return Result.error(BusinessException.notFound('Activity'));
  }

  /// Invalidates search cache when filters change significantly.
  void invalidateSearchCache() {
    _cache.invalidatePrefix('search_results_');
  }

  /// Invalidates all activity-related cache.
  void invalidateAll() {
    _cache.invalidatePrefix('search_');
    _cache.invalidatePrefix('activity_');
  }
}

/// Implementation of [OrganizationRepository] using the API service.
///
/// Follows the same patterns as ActivityRepositoryImpl with caching
/// and proper error handling.
class OrganizationRepositoryImpl implements OrganizationRepository {
  OrganizationRepositoryImpl(this._apiService, {CacheManager? cacheManager})
    : _cache = cacheManager ?? CacheManager.instance;

  // ignore: unused_field - will be used when endpoints are implemented
  final ApiService _apiService;
  final CacheManager _cache;

  @override
  Future<Result<OrganizationEntity>> getOrganization(
    String organizationId,
  ) async {
    final cacheKey = CacheKeys.organization(organizationId);

    return _cache.getOrFetch<OrganizationEntity>(
      key: cacheKey,
      policy: CachePolicy.longLived,
      fetch: () => _fetchOrganization(organizationId),
    );
  }

  Future<Result<OrganizationEntity>> _fetchOrganization(
    String organizationId,
  ) async {
    // For now, we don't have a dedicated endpoint for single organization
    return Result.error(BusinessException.notFound('Organization'));
  }

  @override
  Future<Result<List<ActivitySearchResultEntity>>> getOrganizationActivities(
    String organizationId,
  ) async {
    final cacheKey = CacheKeys.organizationActivities(organizationId);

    return _cache.getOrFetch<List<ActivitySearchResultEntity>>(
      key: cacheKey,
      policy: CachePolicy.api,
      fetch: () => _fetchOrganizationActivities(organizationId),
    );
  }

  Future<Result<List<ActivitySearchResultEntity>>> _fetchOrganizationActivities(
    String organizationId,
  ) async {
    // For now, we don't have a dedicated endpoint for organization activities
    return Result.error(BusinessException.notFound('Organization activities'));
  }
}
