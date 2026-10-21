import '../features/home_wizard/models/home_wizard_choices.dart';
import '../models/geographic_area.dart';
import 'areas_service.dart';
import 'auth_service.dart';

/// Loads the active geographic area tree for search filters.
///
/// Signed-in users receive GET /v1/user/areas (cached via [AreasService]).
/// Guests use a shallow bundled region list so every chip id is searchable.
class GeographicAreaService {
  GeographicAreaService(this._areasService, this._authService);

  final AreasService _areasService;
  final AuthService _authService;
  List<GeographicArea>? _cachedTree;
  bool? _cachedForSignedIn;

  Future<List<GeographicArea>> loadActiveAreaTree() async {
    final signedIn = await _authService.isSignedIn();
    if (_cachedTree != null && _cachedForSignedIn == signedIn) {
      return _cachedTree!;
    }
    final tree = signedIn ? await _loadSignedInTree() : await _guestTree();
    _cachedTree = tree;
    _cachedForSignedIn = signedIn;
    return tree;
  }

  Future<List<GeographicArea>> _loadSignedInTree() async {
    final nodes = await _areasService.getActiveAreaTree();
    return [
      for (final node in nodes)
        if (node.active) GeographicArea.fromNode(node, activeOnly: true),
    ];
  }

  Future<List<GeographicArea>> _guestTree() => _fallbackTree();

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
