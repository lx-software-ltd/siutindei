import 'geographic_area_models.dart';

/// Geographic area node from GET /v1/user/areas.
class GeographicArea {
  const GeographicArea({
    required this.id,
    required this.parentId,
    required this.name,
    required this.level,
    required this.active,
    required this.displayOrder,
    this.code,
    this.children = const [],
  });

  factory GeographicArea.fromNode(GeographicAreaNode node) {
    return GeographicArea(
      id: node.id,
      parentId: node.parentId,
      name: node.name,
      level: node.level,
      code: node.code,
      active: node.active,
      displayOrder: node.displayOrder,
      children: [
        for (final child in node.children) GeographicArea.fromNode(child),
      ],
    );
  }

  factory GeographicArea.fromJson(Map<String, dynamic> json) {
    return GeographicArea(
      id: json['id'] as String,
      parentId: json['parent_id'] as String?,
      name: json['name'] as String,
      level: json['level'] as String? ?? '',
      code: json['code'] as String?,
      active: json['active'] as bool? ?? true,
      displayOrder: json['display_order'] as int? ?? 0,
      children: [
        for (final item in json['children'] as List<dynamic>? ?? [])
          GeographicArea.fromJson(item as Map<String, dynamic>),
      ],
    );
  }

  final String id;
  final String? parentId;
  final String name;
  final String level;
  final String? code;
  final bool active;
  final int displayOrder;
  final List<GeographicArea> children;

  bool get hasChildren => children.isNotEmpty;
}

/// Indexed area tree for chip options and back navigation.
class GeographicAreaTreeIndex {
  GeographicAreaTreeIndex._(this.roots, this._byId, this._parentById);

  final List<GeographicArea> roots;
  final Map<String, GeographicArea> _byId;
  final Map<String, String?> _parentById;

  factory GeographicAreaTreeIndex.fromRoots(List<GeographicArea> roots) {
    final byId = <String, GeographicArea>{};
    final parentById = <String, String?>{};
    void walk(List<GeographicArea> nodes, String? parentId) {
      for (final node in nodes) {
        byId[node.id] = node;
        parentById[node.id] = parentId;
        walk(node.children, node.id);
      }
    }

    walk(roots, null);
    return GeographicAreaTreeIndex._(roots, byId, parentById);
  }

  bool get _hideRoot => roots.length == 1 && roots.first.hasChildren;

  List<GeographicArea> _sorted(List<GeographicArea> nodes) {
    return [...nodes]..sort((a, b) => a.displayOrder.compareTo(b.displayOrder));
  }

  List<GeographicArea> _visibleSorted(List<GeographicArea> nodes) {
    return _sorted([
      for (final node in nodes)
        if (node.active) node,
    ]);
  }

  List<GeographicArea> chipOptions({String? selectedAreaId}) {
    if (roots.isEmpty) {
      return const [];
    }
    var selected = selectedAreaId == null ? null : _byId[selectedAreaId];
    if (selected != null && !selected.active) {
      selected = null;
      selectedAreaId = null;
    }
    if (selected == null) {
      return _hideRoot
          ? _visibleSorted(roots.first.children)
          : _visibleSorted(roots);
    }
    if (selected.hasChildren) {
      return _visibleSorted(selected.children);
    }
    final parent = _byId[_parentById[selectedAreaId]];
    if (parent == null) {
      return _visibleSorted(roots);
    }
    return _visibleSorted(parent.children);
  }

  String? backTarget(String? selectedAreaId) {
    if (selectedAreaId == null) {
      return null;
    }
    final chain = <GeographicArea>[];
    var current = _byId[selectedAreaId];
    while (current != null) {
      chain.insert(0, current);
      final parentId = _parentById[current.id];
      current = parentId == null ? null : _byId[parentId];
    }
    final minLen = _hideRoot ? 2 : 1;
    if (chain.length <= minLen) {
      return null;
    }
    return chain[chain.length - 2].id;
  }
}
