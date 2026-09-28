import 'package:flutter_test/flutter_test.dart';
import 'package:siutindei_app/models/geographic_area_models.dart';

void main() {
  test('parses nested area tree response', () {
    final response = AreaTreeResponse.fromJson({
      'items': [
        {
          'id': 'area-hk',
          'parent_id': null,
          'name': 'Hong Kong',
          'name_translations': {'en': 'Hong Kong'},
          'level': 'country',
          'code': 'HK',
          'active': true,
          'display_order': 1,
          'children': [
            {
              'id': 'area-wanchai',
              'parent_id': 'area-hk',
              'name': 'Wan Chai',
              'name_translations': {'en': 'Wan Chai'},
              'level': 'district',
              'code': null,
              'active': true,
              'display_order': 1,
              'children': [],
            },
          ],
        },
      ],
    });

    expect(response.items, hasLength(1));
    expect(response.items.first.children, hasLength(1));
    expect(response.items.first.children.first.id, 'area-wanchai');
  });
}
