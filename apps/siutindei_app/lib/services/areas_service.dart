import '../core/cache/cache_manager.dart';
import '../core/utils/result.dart';
import '../models/geographic_area_models.dart';
import 'api_service.dart';
import 'bundled_areas_service.dart';

/// Fetches and caches the active geographic area tree.
class AreasService {
  AreasService(this._apiService, {CacheManager? cacheManager})
      : _cache = cacheManager ?? CacheManager.instance;

  final ApiService _apiService;
  final CacheManager _cache;

  static const _cacheKey = 'geographic_areas_tree';

  Future<List<GeographicAreaNode>> getActiveAreaTree() async {
    final result = await _cache.getOrFetch<List<GeographicAreaNode>>(
      key: _cacheKey,
      policy: CachePolicy.longLived,
      fetch: _fetchAreaTree,
    );

    return switch (result) {
      Ok(value: final tree) => tree,
      Error() => await BundledAreasService.loadFromHomeWizard(),
    };
  }

  Future<Result<List<GeographicAreaNode>>> _fetchAreaTree() async {
    try {
      final response = await _apiService.fetchActiveAreas();
      if (response.items.isEmpty) {
        final bundled = await BundledAreasService.loadFromHomeWizard();
        return Result.ok(bundled);
      }
      return Result.ok(response.items);
    } on Object {
      final bundled = await BundledAreasService.loadFromHomeWizard();
      return Result.ok(bundled);
    }
  }
}
