import 'package:flutter_test/flutter_test.dart';
import 'package:siutindei_app/features/search/utils/area_filter_options.dart';
import 'package:siutindei_app/models/geographic_area_models.dart';

void main() {
  group('leafAreaFilterOptions', () {
    test('returns leaf nodes sorted by display order', () {
      final tree = [
        GeographicAreaNode(
          id: 'country',
          name: 'Hong Kong',
          nameTranslations: const {'en': 'Hong Kong'},
          level: 'country',
          active: true,
          displayOrder: 0,
          children: [
            GeographicAreaNode(
              id: 'district-b',
              name: 'B District',
              nameTranslations: const {'en': 'B District'},
              level: 'district',
              active: true,
              displayOrder: 2,
            ),
            GeographicAreaNode(
              id: 'district-a',
              name: 'A District',
              nameTranslations: const {'en': 'A District'},
              level: 'district',
              active: true,
              displayOrder: 1,
            ),
          ],
        ),
      ];

      final options = leafAreaFilterOptions(tree);
      expect(options.map((option) => option.id).toList(), [
        'district-a',
        'district-b',
      ]);
    });

    test('skips inactive nodes', () {
      final tree = [
        GeographicAreaNode(
          id: 'inactive',
          name: 'Hidden',
          nameTranslations: const {'en': 'Hidden'},
          level: 'district',
          active: false,
          displayOrder: 0,
        ),
      ];

      expect(leafAreaFilterOptions(tree), isEmpty);
    });
  });
}
