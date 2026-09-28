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

  factory GeographicArea.fromNode(dynamic node) {
    return GeographicArea(
      id: node.id as String,
      parentId: node.parentId as String?,
      name: node.name as String,
      level: node.level as String? ?? '',
      code: node.code as String?,
      active: node.active as bool? ?? true,
      displayOrder: node.displayOrder as int? ?? 0,
      children: [
        for (final child in node.children as List<dynamic>)
          GeographicArea.fromNode(child),
      ],
    );
  }

  factory GeographicArea.fromJson(Map<String, dynamic> json) {
    final childrenJson = json['children'] as List<dynamic>? ?? [];
    return GeographicArea(
      id: json['id'] as String,
      parentId: json['parent_id'] as String?,
      name: json['name'] as String,
      level: json['level'] as String? ?? '',
      code: json['code'] as String?,
      active: json['active'] as bool? ?? true,
      displayOrder: json['display_order'] as int? ?? 0,
      children: childrenJson
          .map(
            (item) => GeographicArea.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
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

/// Indexed view of an area tree for navigation and chip options.
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
        if (node.children.isNotEmpty) {
          walk(node.children, node.id);
        }
      }
    }

    walk(roots, null);
    return GeographicAreaTreeIndex._(roots, byId, parentById);
  }

  GeographicArea? nodeById(String id) => _byId[id];

  List<GeographicArea> chainFor(String areaId) {
    final chain = <GeographicArea>[];
    var current = _byId[areaId];
    while (current != null) {
      chain.insert(0, current);
      final parentId = _parentById[current.id];
      current = parentId == null ? null : _byId[parentId];
    }
    return chain;
  }

  /// Options shown in the horizontal chip row for the current selection.
  List<GeographicArea> chipOptions({String? selectedAreaId}) {
    if (roots.isEmpty) {
      return const [];
    }

    if (selectedAreaId == null) {
      if (roots.length == 1 && roots.first.hasChildren) {
        return _sortedChildren(roots.first);
      }
      return _sortedRoots();
    }

    final selected = _byId[selectedAreaId];
    if (selected == null) {
      return chipOptions(selectedAreaId: null);
    }

    if (selected.hasChildren) {
      return _sortedChildren(selected);
    }

    final parentId = _parentById[selectedAreaId];
    if (parentId == null) {
      return _sortedRoots();
    }
    final parent = _byId[parentId];
    if (parent == null) {
      return _sortedRoots();
    }
    return _sortedChildren(parent);
  }

  /// Area id to apply when the user taps the back chip, or null to clear.
  String? backTarget(String? selectedAreaId) {
    if (selectedAreaId == null) {
      return null;
    }

    final chain = chainFor(selectedAreaId);
    if (chain.isEmpty) {
      return null;
    }

    if (roots.length == 1) {
      if (chain.length <= 1) {
        return null;
      }
      return chain[chain.length - 2].id;
    }

    if (chain.length <= 1) {
      return null;
    }
    return chain[chain.length - 2].id;
  }

  bool get canNavigateBack => roots.isNotEmpty;

  List<GeographicArea> _sortedRoots() {
    final copy = List<GeographicArea>.from(roots);
    copy.sort((a, b) => a.displayOrder.compareTo(b.displayOrder));
    return copy;
  }

  List<GeographicArea> _sortedChildren(GeographicArea parent) {
    final copy = List<GeographicArea>.from(parent.children);
    copy.sort((a, b) => a.displayOrder.compareTo(b.displayOrder));
    return copy;
  }
}
