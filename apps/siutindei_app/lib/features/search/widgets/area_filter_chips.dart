import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../config/tokens/tokens.dart';
import '../../../models/geographic_area.dart';
import '../../../viewmodels/geographic_areas_provider.dart';
import 'filter_chip_bar.dart';

/// Cascading area filter chips driven by GET /v1/user/areas.
///
/// Watches [geographicAreaTreeProvider] once per session; chip rows are derived
/// in memory via [GeographicAreaTreeIndex] so drill-down stays responsive.
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

    return Semantics(
      container: true,
      label: 'Area filters',
      child: treeAsync.when(
        loading: () => Padding(
          padding: EdgeInsets.symmetric(horizontal: spacing.md),
          child: const LinearProgressIndicator(minHeight: 2),
        ),
        error: (error, _) => Padding(
          padding: EdgeInsets.symmetric(horizontal: spacing.md),
          child: Text(
            'Unable to load areas',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
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
      ),
    );
  }
}
