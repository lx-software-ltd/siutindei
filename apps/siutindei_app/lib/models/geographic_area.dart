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

  factory GeographicArea.fromNode(
    GeographicAreaNode node, {
    bool activeOnly = false,
  }) {
    return GeographicArea(
      id: node.id,
      parentId: node.parentId,
      name: node.name,
      level: node.level,
      code: node.code,
      active: node.active,
      displayOrder: node.displayOrder,
      children: [
        for (final child in node.children)
          if (!activeOnly || child.active)
            GeographicArea.fromNode(child, activeOnly: activeOnly),
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

/// Indexed area tree for cascading search filter chips.
///
/// Top-level options mirror GET /v1/user/areas; selecting a node with children
/// drills in, and Back / All areas walk up or clear the active area filter.
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

  List<GeographicArea> _sortedActive(List<GeographicArea> nodes) {
    final active = nodes.where((node) => node.active).toList();
    active.sort((a, b) => a.displayOrder.compareTo(b.displayOrder));
    return active;
  }

  /// Bundled offline trees use synthetic district ids; skip that row so users
  /// pick real neighbourhood UUIDs that match the search API.
  List<GeographicArea> _flattenBundledDistrictRow(List<GeographicArea> nodes) {
    if (nodes.isEmpty ||
        !nodes.every((node) => node.id.startsWith('bundled-district-'))) {
      return nodes;
    }
    final flattened = <GeographicArea>[];
    for (final district in nodes) {
      flattened.addAll(_sortedActive(district.children));
    }
    return flattened;
  }

  List<GeographicArea> chipOptions({String? selectedAreaId}) {
    if (roots.isEmpty) {
      return const [];
    }
    final selected = selectedAreaId == null ? null : _byId[selectedAreaId];
    List<GeographicArea> options;
    if (selected == null) {
      options = _hideRoot
          ? _sortedActive(roots.first.children)
          : _sortedActive(roots);
    } else if (selected.hasChildren) {
      options = _sortedActive(selected.children);
    } else {
      final parent = _byId[_parentById[selectedAreaId]];
      options = parent == null
          ? _sortedActive(roots)
          : _sortedActive(parent.children);
    }
    return _flattenBundledDistrictRow(options);
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
