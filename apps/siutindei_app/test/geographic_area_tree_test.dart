import 'package:flutter_test/flutter_test.dart';
import 'package:siutindei_app/models/geographic_area.dart';

GeographicArea _node({
  required String id,
  required String name,
  String? parentId,
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
    final index = GeographicAreaTreeIndex.fromRoots([
      _node(
        id: 'country',
        name: 'Hong Kong',
        children: [
          _node(id: 'a', parentId: 'country', name: 'Island'),
          _node(id: 'b', parentId: 'country', name: 'Kowloon'),
        ],
      ),
    ]);
    expect(index.chipOptions().map((n) => n.name), ['Island', 'Kowloon']);
    expect(index.chipOptions(selectedAreaId: 'a').map((n) => n.name), [
      'Island',
      'Kowloon',
    ]);
  });

  test('chipOptions drills into children after parent selection', () {
    final index = GeographicAreaTreeIndex.fromRoots([
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
    ]);
    expect(index.chipOptions(selectedAreaId: 'region').map((n) => n.name), [
      'Mong Kok',
      'Tsim Sha Tsui',
    ]);
  });

  test('chipOptions skips inactive siblings', () {
    final index = GeographicAreaTreeIndex.fromRoots([
      _node(
        id: 'country',
        name: 'Hong Kong',
        children: [
          _node(id: 'a', parentId: 'country', name: 'Island'),
          GeographicArea(
            id: 'hidden',
            parentId: 'country',
            name: 'Hidden',
            level: 'region',
            active: false,
            displayOrder: 2,
          ),
        ],
      ),
    ]);
    expect(index.chipOptions().map((n) => n.name), ['Island']);
  });

  test('chipOptions flattens bundled district row to neighbourhoods', () {
    final index = GeographicAreaTreeIndex.fromRoots([
      _node(
        id: 'region',
        parentId: 'country',
        name: 'Kowloon',
        children: [
          _node(
            id: 'bundled-district-region-0',
            parentId: 'region',
            name: 'District',
            children: [
              _node(id: 'n1', parentId: 'bundled-district-region-0', name: 'A'),
              _node(id: 'n2', parentId: 'bundled-district-region-0', name: 'B'),
            ],
          ),
        ],
      ),
    ]);
    expect(
      index.chipOptions(selectedAreaId: 'region').map((n) => n.name),
      ['A', 'B'],
    );
  });

  test('backTarget clears single-country first level selection', () {
    final index = GeographicAreaTreeIndex.fromRoots([
      _node(
        id: 'country',
        name: 'Hong Kong',
        children: [_node(id: 'a', parentId: 'country', name: 'Island')],
      ),
    ]);
    expect(index.backTarget('a'), isNull);
    expect(index.backTarget('country'), isNull);
  });
}
