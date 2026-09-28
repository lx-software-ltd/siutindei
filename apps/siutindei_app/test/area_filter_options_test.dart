import 'package:flutter_test/flutter_test.dart';
import 'package:siutindei_app/features/search/utils/area_filter_options.dart';
import 'package:siutindei_app/models/geographic_area_models.dart';
import 'package:siutindei_app/services/areas_service.dart';

GeographicAreaNode _node({
  required String id,
  required String name,
  bool active = true,
  int displayOrder = 0,
  List<GeographicAreaNode> children = const [],
}) {
  return GeographicAreaNode(
    id: id,
    name: name,
    nameTranslations: {'en': name},
    level: 'district',
    active: active,
    displayOrder: displayOrder,
    children: children,
  );
}

void main() {
  test('leafAreaFilterOptions sorts leaves and skips inactive', () {
    final options = leafAreaFilterOptions([
      _node(
        id: 'country',
        name: 'Hong Kong',
        children: [
          _node(id: 'district-b', name: 'B District', displayOrder: 2),
          _node(id: 'district-a', name: 'A District', displayOrder: 1),
        ],
      ),
      _node(id: 'inactive', name: 'Hidden', active: false),
    ]);
    expect(options.map((o) => o.id), ['district-a', 'district-b']);
  });

  test('bundled home wizard tree exposes region area ids', () async {
    TestWidgetsFlutterBinding.ensureInitialized();
    final options = leafAreaFilterOptions(await AreasService.loadBundledAreas());
    expect(options, isNotEmpty);
    expect(
      options.map((o) => o.id),
      contains('a1111111-1111-1111-1111-111111111101'),
    );
  });
}
