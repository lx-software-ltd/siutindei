import '../features/home_wizard/models/home_wizard_choices.dart';
import '../models/geographic_area.dart';
import 'api_service.dart';
import 'auth_service.dart';

/// Loads the active geographic area tree, with a bundled fallback.
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
      } on Object {
        // Use bundled regions when the API is unavailable.
      }
    }
    final fallback = await _fallbackTree();
    _cachedTree = fallback;
    _cachedForSignedIn = signedIn;
    return fallback;
  }

  static Future<List<GeographicArea>> _fallbackTree() async {
    final regions = (await HomeWizardChoices.loadFromAsset()).regions;
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
          for (var i = 0; i < regions.length; i++)
            GeographicArea(
              id: regions[i].areaId,
              parentId: countryId,
              name: regions[i].labels.en,
              level: 'region',
              active: true,
              displayOrder: i + 1,
            ),
        ],
      ),
    ];
  }
}
