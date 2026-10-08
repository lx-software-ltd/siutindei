import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/geographic_area_models.dart';
import '../../../services/service_providers.dart';
import '../utils/area_filter_options.dart';
import 'filter_chip_bar.dart';

final geographicAreasProvider = FutureProvider<List<GeographicAreaNode>>((ref) {
  return ref.watch(areasServiceProvider).getActiveAreaTree();
});

class AreaFilterSection extends ConsumerWidget {
  const AreaFilterSection({
    super.key,
    required this.selectedAreaId,
    required this.onAreaSelected,
    this.locale = 'en',
  });

  final String? selectedAreaId;
  final ValueChanged<String?> onAreaSelected;
  final String locale;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ref
        .watch(geographicAreasProvider)
        .when(
          loading: () => const LinearProgressIndicator(minHeight: 2),
          error: (_, _) => const Text(
            'Unable to load areas',
            style: TextStyle(color: Colors.grey),
          ),
          data: (tree) {
            final options = leafAreaFilterOptions(tree, locale: locale);
            if (options.isEmpty) {
              return const Text(
                'No areas available',
                style: TextStyle(color: Colors.grey),
              );
            }
            return Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final option in options)
                  FilterChip(
                    label: Text(option.label),
                    selected: selectedAreaId == option.id,
                    onSelected: (selected) {
                      onAreaSelected(
                        !selected || selectedAreaId == option.id
                            ? null
                            : option.id,
                      );
                    },
                  ),
              ],
            );
          },
        );
  }
}

class AreaDropdownFilterChip extends ConsumerWidget {
  const AreaDropdownFilterChip({
    super.key,
    required this.selectedAreaId,
    required this.onAreaChanged,
    this.locale = 'en',
  });

  final String? selectedAreaId;
  final ValueChanged<String?> onAreaChanged;
  final String locale;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ref
        .watch(geographicAreasProvider)
        .when(
          loading: () => const SizedBox.shrink(),
          error: (_, _) => const SizedBox.shrink(),
          data: (tree) {
            final options = leafAreaFilterOptions(tree, locale: locale);
            if (options.isEmpty) {
              return const SizedBox.shrink();
            }
            final labels = areaFilterLabelLookup(options);
            return DropdownFilterChip(
              label: 'Area',
              value: selectedAreaId,
              options: options.map((option) => option.id).toList(),
              displayNameBuilder: (id) => labels[id] ?? id,
              onChanged: onAreaChanged,
            );
          },
        );
  }
}
