import '../../../models/geographic_area_models.dart';

class AreaFilterOption {
  const AreaFilterOption({required this.id, required this.label});

  final String id;
  final String label;
}

/// Active leaf nodes from the geographic area tree.
List<AreaFilterOption> leafAreaFilterOptions(
  List<GeographicAreaNode> roots, {
  String locale = 'en',
}) {
  final leaves = <GeographicAreaNode>[];
  void visit(GeographicAreaNode node) {
    if (!node.active) {
      return;
    }
    if (node.children.isEmpty) {
      leaves.add(node);
      return;
    }
    for (final child in node.children) {
      visit(child);
    }
  }

  for (final root in roots) {
    visit(root);
  }
  leaves.sort((a, b) => a.displayOrder.compareTo(b.displayOrder));
  return [
    for (final node in leaves)
      AreaFilterOption(id: node.id, label: node.labelForLocale(locale)),
  ];
}

Map<String, String> areaFilterLabelLookup(List<AreaFilterOption> options) {
  return {for (final option in options) option.id: option.label};
}
