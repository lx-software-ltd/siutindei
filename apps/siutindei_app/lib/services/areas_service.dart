import '../core/cache/cache_manager.dart';
import '../core/utils/result.dart';
import '../features/home_wizard/models/home_wizard_choices.dart';
import '../models/geographic_area_models.dart';
import 'api_service.dart';

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
      Error() => await loadBundledAreas(),
    };
  }

  Future<Result<List<GeographicAreaNode>>> _fetchAreaTree() async {
    try {
      final items = (await _apiService.fetchActiveAreas()).items;
      return Result.ok(items.isEmpty ? await loadBundledAreas() : items);
    } on Object {
      return Result.ok(await loadBundledAreas());
    }
  }

  static Future<List<GeographicAreaNode>> loadBundledAreas() async {
    final regions = (await HomeWizardChoices.loadFromAsset()).regions;
    if (regions.isEmpty) {
      return const [];
    }
    return [
      GeographicAreaNode(
        id: 'bundled-hong-kong',
        name: 'Hong Kong',
        nameTranslations: const {'en': 'Hong Kong'},
        level: 'country',
        code: 'HK',
        active: true,
        displayOrder: 0,
        children: [
          for (var i = 0; i < regions.length; i++)
            GeographicAreaNode(
              id: regions[i].areaId,
              parentId: 'bundled-hong-kong',
              name: regions[i].labels.en,
              nameTranslations: {
                'en': regions[i].labels.en,
                'zh-HK': regions[i].labels.zhHk,
              },
              level: 'region',
              active: true,
              displayOrder: i,
            ),
        ],
      ),
    ];
  }
}
