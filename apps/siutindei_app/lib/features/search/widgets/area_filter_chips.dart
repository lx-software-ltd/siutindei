import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../config/tokens/tokens.dart';
import '../../../models/geographic_area.dart';
import '../../../viewmodels/geographic_areas_provider.dart';
import 'filter_chip_bar.dart';

/// Cascading area filter chips driven by GET /v1/user/areas.
class AreaFilterChips extends ConsumerWidget {
  const AreaFilterChips({
    super.key,
    required this.selectedAreaId,
    required this.onAreaChanged,
  });

  final String? selectedAreaId;
  final ValueChanged<String?> onAreaChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final treeAsync = ref.watch(geographicAreaTreeProvider);
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));

    return treeAsync.when(
      loading: () => Padding(
        padding: EdgeInsets.symmetric(horizontal: spacing.md),
        child: const LinearProgressIndicator(minHeight: 2),
      ),
      error: (_, __) => const SizedBox.shrink(),
      data: (roots) {
        if (roots.isEmpty) {
          return const SizedBox.shrink();
        }

        final index = GeographicAreaTreeIndex.fromRoots(roots);
        final options = index.chipOptions(selectedAreaId: selectedAreaId);
        if (options.isEmpty) {
          return const SizedBox.shrink();
        }

        final backTarget = index.backTarget(selectedAreaId);

        return FilterChipBar(
          children: [
            if (selectedAreaId != null)
              TokenFilterChip(
                label: 'All areas',
                selected: false,
                onSelected: (_) => onAreaChanged(null),
              ),
            if (backTarget != null)
              TokenFilterChip(
                label: 'Back',
                selected: false,
                onSelected: (_) => onAreaChanged(backTarget),
              ),
            for (final area in options)
              TokenFilterChip(
                label: area.name,
                selected: selectedAreaId == area.id,
                onSelected: (_) => onAreaChanged(area.id),
              ),
          ],
        );
      },
    );
  }
}

/// Multi-level area chips for the filters sheet (wrap layout).
class AreaFilterChipWrap extends ConsumerWidget {
  const AreaFilterChipWrap({
    super.key,
    required this.selectedAreaId,
    required this.onAreaChanged,
  });

  final String? selectedAreaId;
  final ValueChanged<String?> onAreaChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final treeAsync = ref.watch(geographicAreaTreeProvider);

    return treeAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (_, __) => const Text(
        'Unable to load areas',
        style: TextStyle(color: Colors.grey),
      ),
      data: (roots) {
        if (roots.isEmpty) {
          return const Text(
            'No areas available',
            style: TextStyle(color: Colors.grey),
          );
        }

        final index = GeographicAreaTreeIndex.fromRoots(roots);
        final levels = _levelsForSelection(index, selectedAreaId);
        if (levels.isEmpty) {
          return const SizedBox.shrink();
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (var levelIndex = 0; levelIndex < levels.length; levelIndex++)
              Padding(
                padding: EdgeInsets.only(bottom: levelIndex == levels.length - 1 ? 0 : 8),
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: levels[levelIndex].map((area) {
                    final isSelected = _isSelectedAtLevel(
                      index,
                      selectedAreaId,
                      area,
                      levelIndex,
                    );
                    return FilterChip(
                      label: Text(area.name),
                      selected: isSelected,
                      onSelected: (selected) {
                        if (selected) {
                          onAreaChanged(area.id);
                        } else if (selectedAreaId == area.id) {
                          onAreaChanged(index.backTarget(area.id));
                        }
                      },
                    );
                  }).toList(),
                ),
              ),
          ],
        );
      },
    );
  }

  List<List<GeographicArea>> _levelsForSelection(
    GeographicAreaTreeIndex index,
    String? selectedAreaId,
  ) {
    final levels = <List<GeographicArea>>[
      index.chipOptions(selectedAreaId: null),
    ];

    if (selectedAreaId == null) {
      return levels;
    }

    final chain = index.chainFor(selectedAreaId);
    for (final node in chain) {
      if (node.hasChildren) {
        levels.add(index.chipOptions(selectedAreaId: node.id));
      }
    }
    return levels;
  }

  bool _isSelectedAtLevel(
    GeographicAreaTreeIndex index,
    String? selectedAreaId,
    GeographicArea area,
    int levelIndex,
  ) {
    if (selectedAreaId == null) {
      return false;
    }
    final chain = index.chainFor(selectedAreaId);
    if (levelIndex >= chain.length) {
      return false;
    }
    return chain[levelIndex].id == area.id;
  }
}
