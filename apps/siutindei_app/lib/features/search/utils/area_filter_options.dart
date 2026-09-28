import '../../../models/geographic_area_models.dart';

/// Selectable area shown in search filters.
class AreaFilterOption {
  const AreaFilterOption({
    required this.id,
    required this.label,
  });

  final String id;
  final String label;
}

/// Collects leaf nodes from the geographic area tree for filtering.
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

  leaves.sort((left, right) => left.displayOrder.compareTo(right.displayOrder));

  return leaves
      .map(
        (node) => AreaFilterOption(
          id: node.id,
          label: node.labelForLocale(locale),
        ),
      )
      .toList();
}

Map<String, String> areaFilterLabelLookup(List<AreaFilterOption> options) {
  return {for (final option in options) option.id: option.label};
}
