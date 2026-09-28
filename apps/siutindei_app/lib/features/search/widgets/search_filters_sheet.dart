import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../config/constants.dart';
import '../../../config/tokens/tokens.dart';
import '../../../domain/entities/entities.dart';
import 'area_filter_chips.dart';

/// Advanced search filters bottom sheet using leaf tokens.
///
/// Uses domain entities (SearchFilters) for type safety.
class SearchFiltersSheet extends ConsumerStatefulWidget {
  const SearchFiltersSheet({
    super.key,
    required this.initialFilters,
    required this.onApply,
  });

  final SearchFilters initialFilters;
  final ValueChanged<SearchFilters> onApply;

  static Future<void> show({
    required BuildContext context,
    required SearchFilters initialFilters,
    required ValueChanged<SearchFilters> onApply,
  }) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (context) => SearchFiltersSheet(
        initialFilters: initialFilters,
        onApply: onApply,
      ),
    );
  }

  @override
  ConsumerState<SearchFiltersSheet> createState() => _SearchFiltersSheetState();
}

class _SearchFiltersSheetState extends ConsumerState<SearchFiltersSheet> {
  late SearchFilters _filters;
  final _ageController = TextEditingController();
  final _priceMinController = TextEditingController();
  final _priceMaxController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _filters = widget.initialFilters;
    _ageController.text = _filters.age?.toString() ?? '';
    _priceMinController.text = _filters.priceMin?.toString() ?? '';
    _priceMaxController.text = _filters.priceMax?.toString() ?? '';
  }

  @override
  void dispose() {
    _ageController.dispose();
    _priceMinController.dispose();
    _priceMaxController.dispose();
    super.dispose();
  }

  void _updateFilters(SearchFilters Function(SearchFilters) updater) {
    setState(() => _filters = updater(_filters));
  }

  void _clearAll() {
    setState(() {
      _filters = SearchFilters.empty;
      _ageController.clear();
      _priceMinController.clear();
      _priceMaxController.clear();
    });
  }

  void _applyFilters() {
    final age = int.tryParse(_ageController.text);
    final priceMin = double.tryParse(_priceMinController.text);
    final priceMax = double.tryParse(_priceMaxController.text);

    final updatedFilters = _filters.copyWith(
      age: age,
      priceMin: priceMin,
      priceMax: priceMax,
      clearAge: age == null,
      clearPriceMin: priceMin == null,
      clearPriceMax: priceMax == null,
    );

    widget.onApply(updatedFilters);
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final semantic = ref.watch(semanticTokensProvider);
    final bottomSheet = ref.watch(componentTokensProvider).bottomSheet;
    final chip = ref.watch(componentTokensProvider).chip;

    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (context, scrollController) => Column(
        children: [
          _buildHeader(semantic, bottomSheet),
          Expanded(
            child: ListView(
              controller: scrollController,
              padding: EdgeInsets.all(semantic.spacing.md),
              children: [
                _buildSection('Child Age', _buildAgeSection(semantic, chip)),
                SizedBox(height: semantic.spacing.lg),
                _buildSection('Area', _buildAreaSection()),
                SizedBox(height: semantic.spacing.lg),
                _buildSection('Price Range', _buildPriceSection(semantic)),
                SizedBox(height: semantic.spacing.lg),
                _buildSection('Pricing Type', _buildPricingTypeSection(chip)),
                SizedBox(height: semantic.spacing.lg),
                _buildSection('Day of Week', _buildDayOfWeekSection(chip)),
                SizedBox(height: semantic.spacing.lg),
                _buildSection('Languages', _buildLanguagesSection(chip)),
                SizedBox(height: semantic.spacing.xl),
              ],
            ),
          ),
          _buildApplyButton(semantic),
        ],
      ),
    );
  }

  Widget _buildHeader(SemanticTokens semantic, BottomSheetTokens bottomSheet) {
    return Container(
      padding: EdgeInsets.all(semantic.spacing.md),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: semantic.color.border)),
      ),
      child: Row(
        children: [
          Text('Filters', style: semantic.text.titleMedium),
          const Spacer(),
          TextButton(onPressed: _clearAll, child: const Text('Clear all')),
          IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.close),
          ),
        ],
      ),
    );
  }

  Widget _buildSection(String title, Widget child) {
    final semantic = ref.watch(semanticTokensProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: semantic.text.labelLarge),
        SizedBox(height: semantic.spacing.sm),
        child,
      ],
    );
  }

  Widget _buildAgeSection(SemanticTokens semantic, ChipTokens chip) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: _ageController,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(
            hintText: 'Enter age',
            prefixIcon: Icon(Icons.child_care),
          ),
        ),
        SizedBox(height: semantic.spacing.sm),
        Wrap(
          spacing: 8,
          children: AppConstants.agePresets.entries.map((entry) {
            return ActionChip(
              label: Text(entry.key),
              onPressed: () => _ageController.text = entry.value.toString(),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildAreaSection() {
    return AreaFilterChips(
      selectedAreaId: _filters.areaId,
      onAreaChanged: (areaId) {
        _updateFilters(
          (filters) => filters.copyWith(
            areaId: areaId,
            clearAreaId: areaId == null,
          ),
        );
      },
    );
  }

  Widget _buildPriceSection(SemanticTokens semantic) {
    return Row(
      children: [
        Expanded(
          child: TextField(
            controller: _priceMinController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              hintText: 'Min',
              prefixText: '\$ ',
            ),
          ),
        ),
        Padding(
          padding: EdgeInsets.symmetric(horizontal: semantic.spacing.sm),
          child: const Text('—'),
        ),
        Expanded(
          child: TextField(
            controller: _priceMaxController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              hintText: 'Max',
              prefixText: '\$ ',
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPricingTypeSection(ChipTokens chipTokens) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: AppConstants.pricingTypes.entries.map((entry) {
        final isSelected = _filters.pricingType?.toApiString() == entry.key;
        return FilterChip(
          label: Text(entry.value),
          selected: isSelected,
          onSelected: (selected) {
            _updateFilters((f) => f.copyWith(
                  pricingType: selected ? PricingType.fromString(entry.key) : null,
                  clearPricingType: !selected,
                ));
          },
        );
      }).toList(),
    );
  }

  Widget _buildDayOfWeekSection(ChipTokens chipTokens) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: List.generate(7, (index) {
        final isSelected = _filters.dayOfWeekUtc == index;
        return FilterChip(
          label: Text(AppConstants.daysOfWeekShort[index]),
          selected: isSelected,
          onSelected: (selected) {
            _updateFilters((f) => f.copyWith(
                  dayOfWeekUtc: selected ? index : null,
                  clearDayOfWeekUtc: !selected,
                ));
          },
        );
      }),
    );
  }

  Widget _buildLanguagesSection(ChipTokens chipTokens) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: AppConstants.languageOptions.entries.map((entry) {
        final isSelected = _filters.languages.contains(entry.key);
        return FilterChip(
          label: Text(entry.value),
          selected: isSelected,
          onSelected: (selected) {
            final newLanguages = List<String>.from(_filters.languages);
            if (selected) {
              newLanguages.add(entry.key);
            } else {
              newLanguages.remove(entry.key);
            }
            _updateFilters((f) => f.copyWith(languages: newLanguages));
          },
        );
      }).toList(),
    );
  }

  Widget _buildApplyButton(SemanticTokens semantic) {
    final filterCount = _filters.activeFilterCount;
    return Container(
      padding: EdgeInsets.all(semantic.spacing.md),
      decoration: BoxDecoration(
        color: semantic.color.surface,
        border: Border(top: BorderSide(color: semantic.color.border)),
      ),
      child: SafeArea(
        child: SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: _applyFilters,
            child: Text(
              filterCount > 0
                  ? 'Apply $filterCount filter${filterCount > 1 ? 's' : ''}'
                  : 'Apply filters',
            ),
          ),
        ),
      ),
    );
  }
}
