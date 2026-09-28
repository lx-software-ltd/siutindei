import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/geographic_areas_provider.dart';
import '../utils/area_filter_options.dart';
import 'filter_chip_bar.dart';

/// Area filter chips backed by GET /v1/user/areas (with offline fallback).
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
    final areasAsync = ref.watch(geographicAreasProvider);

    return areasAsync.when(
      loading: () => const LinearProgressIndicator(minHeight: 2),
      error: (_, __) => const Text(
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
          children: options.map((option) {
            final isSelected = selectedAreaId == option.id;
            return FilterChip(
              label: Text(option.label),
              selected: isSelected,
              onSelected: (selected) {
                if (!selected || isSelected) {
                  onAreaSelected(null);
                } else {
                  onAreaSelected(option.id);
                }
              },
            );
          }).toList(),
        );
      },
    );
  }
}

/// Dropdown chip for the quick-filter row.
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
    final areasAsync = ref.watch(geographicAreasProvider);

    return areasAsync.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
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
