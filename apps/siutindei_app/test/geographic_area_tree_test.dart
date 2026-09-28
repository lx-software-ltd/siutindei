import 'package:flutter_test/flutter_test.dart';
import 'package:siutindei_app/models/geographic_area.dart';

GeographicArea _node({
  required String id,
  String? parentId,
  required String name,
  List<GeographicArea> children = const [],
}) {
  return GeographicArea(
    id: id,
    parentId: parentId,
    name: name,
    level: 'region',
    active: true,
    displayOrder: 1,
    children: children,
  );
}

void main() {
  test('chipOptions uses children when only one country is active', () {
    final tree = [
      _node(
        id: 'country',
        name: 'Hong Kong',
        children: [
          _node(id: 'a', parentId: 'country', name: 'Island'),
          _node(id: 'b', parentId: 'country', name: 'Kowloon'),
        ],
      ),
    ];
    final index = GeographicAreaTreeIndex.fromRoots(tree);

    expect(index.chipOptions(), hasLength(2));
    expect(index.chipOptions().map((n) => n.name), ['Island', 'Kowloon']);
    expect(index.chipOptions(selectedAreaId: 'a').map((n) => n.name), ['Island', 'Kowloon']);
  });

  test('chipOptions drills into children after parent selection', () {
    final tree = [
      _node(
        id: 'country',
        name: 'Hong Kong',
        children: [
          _node(
            id: 'region',
            parentId: 'country',
            name: 'Kowloon',
            children: [
              _node(id: 'd1', parentId: 'region', name: 'Mong Kok'),
              _node(id: 'd2', parentId: 'region', name: 'Tsim Sha Tsui'),
            ],
          ),
        ],
      ),
    ];
    final index = GeographicAreaTreeIndex.fromRoots(tree);

    expect(
      index.chipOptions(selectedAreaId: 'region').map((n) => n.name),
      ['Mong Kok', 'Tsim Sha Tsui'],
    );
  });

  test('backTarget clears single-country first level selection', () {
    final tree = [
      _node(
        id: 'country',
        name: 'Hong Kong',
        children: [
          _node(id: 'a', parentId: 'country', name: 'Island'),
        ],
      ),
    ];
    final index = GeographicAreaTreeIndex.fromRoots(tree);

    expect(index.backTarget('a'), isNull);
    expect(index.backTarget('country'), isNull);
  });
}
