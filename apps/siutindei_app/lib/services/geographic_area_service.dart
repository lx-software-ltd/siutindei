import '../features/home_wizard/models/home_wizard_choices.dart';
import '../models/geographic_area.dart';
import 'api_service.dart';
import 'auth_service.dart';

/// Loads and caches the active geographic area tree.
class GeographicAreaService {
  GeographicAreaService(this._apiService, this._authService);

  final ApiService _apiService;
  final AuthService _authService;

  List<GeographicArea>? _cachedTree;
  bool? _cachedForSignedIn;

  Future<List<GeographicArea>> loadActiveAreaTree() async {
    final signedIn = await _authService.isSignedIn();
    if (_cachedTree != null && _cachedForSignedIn == signedIn) {
      return _cachedTree!;
    }
    if (signedIn) {
      try {
        final tree = [
          for (final node in (await _apiService.fetchActiveAreas()).items)
            GeographicArea.fromNode(node),
        ];
        if (tree.isNotEmpty) {
          _cachedTree = tree;
          _cachedForSignedIn = signedIn;
          return tree;
        }
      } catch (_) {
        // Fall through to bundled fallback for offline / staging.
      }
    }

    final fallback = await _fallbackTreeFromHomeWizard();
    _cachedTree = fallback;
    _cachedForSignedIn = signedIn;
    return fallback;
  }

  void clearCache() {
    _cachedTree = null;
    _cachedForSignedIn = null;
  }

  static Future<List<GeographicArea>> _fallbackTreeFromHomeWizard() async {
    final choices = await HomeWizardChoices.loadFromAsset();
    final regions = choices.regions;
    if (regions.isEmpty) {
      return const [];
    }

    const countryId = 'fallback-country-hk';
    return [
      GeographicArea(
        id: countryId,
        parentId: null,
        name: 'Hong Kong',
        level: 'country',
        code: 'HK',
        active: true,
        displayOrder: 1,
        children: [
          for (var index = 0; index < regions.length; index++)
            GeographicArea(
              id: regions[index].areaId,
              parentId: countryId,
              name: regions[index].labels.en,
              level: 'region',
              active: true,
              displayOrder: index + 1,
            ),
        ],
      ),
    ];
  }
}
