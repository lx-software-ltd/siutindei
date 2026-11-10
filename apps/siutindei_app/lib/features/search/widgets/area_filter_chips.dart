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
class AreaFilterChips extends ConsumerStatefulWidget {
  const AreaFilterChips({
    super.key,
    required this.selectedAreaId,
    required this.onAreaChanged,
    this.allowedAreaIds,
  });

  final String? selectedAreaId;
  final ValueChanged<String?> onAreaChanged;

  /// Neighbourhood ids from `area_scope`. Null shows every area.
  final Set<String>? allowedAreaIds;

  @override
  ConsumerState<AreaFilterChips> createState() => _AreaFilterChipsState();
}

class _AreaFilterChipsState extends ConsumerState<AreaFilterChips> {
  String? _clearRequestedFor;

  @override
  Widget build(BuildContext context) {
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
          final allowed = widget.allowedAreaIds;
          final selected = widget.selectedAreaId;
          if (allowed != null &&
              selected != null &&
              !index.intersectsAllowed(selected, allowed) &&
              _clearRequestedFor != selected) {
            _clearRequestedFor = selected;
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (!mounted || widget.selectedAreaId != selected) {
                return;
              }
              widget.onAreaChanged(null);
            });
          }
          final options = index.chipOptions(
            selectedAreaId: selected,
            allowedAreaIds: allowed,
          );
          if (options.isEmpty) {
            return const SizedBox.shrink();
          }
          final backTarget = index.backTarget(selected);
          return FilterChipBar(
            children: [
              if (selected != null)
                TokenFilterChip(
                  label: 'All areas',
                  selected: false,
                  onSelected: (_) => widget.onAreaChanged(null),
                ),
              if (backTarget != null)
                TokenFilterChip(
                  label: 'Back',
                  selected: false,
                  onSelected: (_) => widget.onAreaChanged(backTarget),
                ),
              for (final area in options)
                TokenFilterChip(
                  label: area.name,
                  selected: selected == area.id,
                  onSelected: (_) => widget.onAreaChanged(area.id),
                ),
            ],
          );
        },
      ),
    );
  }
}
