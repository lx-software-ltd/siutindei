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
    final choices = await HomeWizardChoices.loadFromAsset();
    final regions = choices.regions;
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
              children: _districtNodes(
                regions[i].areaId,
                [
                  for (final neighbourhood in choices.neighbourhoods)
                    if (neighbourhood.regionId == regions[i].id) neighbourhood,
                ],
              ),
            ),
        ],
      ),
    ];
  }

  static List<GeographicAreaNode> _districtNodes(
    String regionAreaId,
    List<WizardNeighbourhoodOption> neighbourhoods,
  ) {
    final grouped = <String, List<WizardNeighbourhoodOption>>{};
    for (final neighbourhood in neighbourhoods) {
      final name = neighbourhood.district.isEmpty
          ? neighbourhood.labels.en
          : neighbourhood.district;
      grouped.putIfAbsent(name, () => []).add(neighbourhood);
    }
    final names = grouped.keys.toList();
    return [
      for (var index = 0; index < names.length; index++)
        _districtNode(
          regionAreaId,
          names[index],
          grouped[names[index]]!,
          index,
        ),
    ];
  }

  static GeographicAreaNode _districtNode(
    String regionAreaId,
    String name,
    List<WizardNeighbourhoodOption> neighbourhoods,
    int index,
  ) {
    final districtId = 'bundled-district-$regionAreaId-$index';
    return GeographicAreaNode(
      id: districtId,
      parentId: regionAreaId,
      name: name,
      nameTranslations: {'en': name},
      level: 'district',
      active: true,
      displayOrder: index,
      children: [
        for (var child = 0; child < neighbourhoods.length; child++)
          GeographicAreaNode(
            id: neighbourhoods[child].areaId,
            parentId: districtId,
            name: neighbourhoods[child].labels.en,
            nameTranslations: {
              'en': neighbourhoods[child].labels.en,
              'zh-HK': neighbourhoods[child].labels.zhHk,
            },
            level: 'neighbourhood',
            active: true,
            displayOrder: child,
          ),
      ],
    );
  }
}
