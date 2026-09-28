import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart' show ScrollCacheExtent;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../config/constants.dart';
import '../../../config/tokens/tokens.dart';
import '../../../domain/entities/entities.dart';
import '../../../viewmodels/activities_viewmodel.dart';
import '../../../viewmodels/auth_viewmodel.dart';
import '../../activity_detail/screens/activity_detail_screen.dart';
import '../../auth/screens/login_screen.dart';
import '../../organization/screens/organization_screen.dart';
import '../widgets/activity_card.dart';
import '../widgets/area_filter_chips.dart';
import '../widgets/filter_chip_bar.dart';
import '../widgets/search_filters_sheet.dart';

/// Main search screen using the design token system and layered architecture.
///
/// Architecture:
/// - Uses domain entities (SearchFilters, ActivitySearchResultEntity)
/// - Consumes state from ActivitiesViewModel via Riverpod
/// - Delegates business logic to use cases via the ViewModel
///
/// Performance optimizations:
/// - Uses `select` for granular Riverpod watching
/// - Extracts static content to separate widgets
/// - Uses RepaintBoundary for expensive static content
/// - Avoids unnecessary object allocations in build
///
/// See: https://docs.flutter.dev/app-architecture/guide
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _performSearch());
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      final state = ref.read(activitiesViewModelProvider);
      if (!state.isLoading && !state.isLoadingMore && state.hasMore) {
        _loadMore();
      }
    }
  }

  void _performSearch() {
    final searchQuery = _searchController.text.trim();
    final currentFilters = ref.read(activitiesFiltersProvider);
    final filters = currentFilters.copyWith(
      searchQuery: searchQuery.isEmpty ? null : searchQuery,
      clearSearchQuery: searchQuery.isEmpty,
    );
    ref.read(activitiesViewModelProvider.notifier).search(filters);
  }

  void _loadMore() {
    ref.read(activitiesViewModelProvider.notifier).loadMore();
  }

  void _updateFilters(SearchFilters filters) {
    ref.read(activitiesViewModelProvider.notifier).search(filters);
  }

  void _showFiltersSheet() {
    final currentFilters = ref.read(activitiesFiltersProvider);
    SearchFiltersSheet.show(
      context: context,
      initialFilters: currentFilters,
      onApply: _updateFilters,
    );
  }

  void _toggleDayFilter(int dayOfWeek) {
    final currentFilters = ref.read(activitiesFiltersProvider);
    if (currentFilters.dayOfWeekUtc == dayOfWeek) {
      _updateFilters(currentFilters.copyWith(clearDayOfWeekUtc: true));
    } else {
      _updateFilters(currentFilters.copyWith(dayOfWeekUtc: dayOfWeek));
    }
  }

  void _toggleAreaFilter(String? areaId) {
    final currentFilters = ref.read(activitiesFiltersProvider);
    if (currentFilters.areaId == areaId || areaId == null) {
      _updateFilters(currentFilters.copyWith(clearAreaId: true));
    } else {
      _updateFilters(currentFilters.copyWith(areaId: areaId));
    }
  }

  void _clearFilters() {
    _searchController.clear();
    ref.read(activitiesViewModelProvider.notifier).search(SearchFilters.empty);
  }

  @override
  Widget build(BuildContext context) {
    // Watch only what's needed using select
    final isSignedIn = ref.watch(
      authViewModelProvider.select((s) => s.isSignedIn),
    );

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Header is static except for auth state
            _SearchHeader(
              isSignedIn: isSignedIn,
              onAuthTap: _handleAuthTap,
            ),
            _SearchBar(
              controller: _searchController,
              onSearch: _performSearch,
            ),
            _QuickFilters(
              onFilterBadgeTap: _showFiltersSheet,
              onDayTap: _toggleDayFilter,
              onAreaChanged: _toggleAreaFilter,
              onPricingTypeChanged: (value) {
                final currentFilters = ref.read(activitiesFiltersProvider);
                if (value == null) {
                  _updateFilters(currentFilters.copyWith(clearPricingType: true));
                } else {
                  _updateFilters(currentFilters.copyWith(
                    pricingType: PricingType.fromString(value),
                  ));
                }
              },
              onScheduleTypeChanged: (value) {
                final currentFilters = ref.read(activitiesFiltersProvider);
                if (value == null) {
                  _updateFilters(currentFilters.copyWith(clearScheduleType: true));
                } else {
                  _updateFilters(currentFilters.copyWith(
                    scheduleType: ScheduleType.fromString(value),
                  ));
                }
              },
            ),
            Expanded(
              child: _ResultsList(
                scrollController: _scrollController,
                onRefresh: _performSearch,
                onClearFilters: _clearFilters,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _handleAuthTap() {
    final isSignedIn = ref.read(authViewModelProvider).isSignedIn;
    if (isSignedIn) {
      ref.read(authViewModelProvider.notifier).signOut();
    } else {
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => const LoginScreen()),
      );
    }
  }
}

/// Extracted header widget - rebuilds only when auth state changes.
class _SearchHeader extends ConsumerWidget {
  const _SearchHeader({
    required this.isSignedIn,
    required this.onAuthTap,
  });

  final bool isSignedIn;
  final VoidCallback onAuthTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));
    final textStyles = ref.watch(semanticTokensProvider.select((s) => s.text));

    return Padding(
      padding: EdgeInsets.fromLTRB(
        spacing.md,
        spacing.md,
        spacing.md,
        spacing.sm,
      ),
      child: Row(
        children: [
          // Static content wrapped in RepaintBoundary
          Expanded(
            child: RepaintBoundary(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Find Activities', style: textStyles.headlineMedium),
                  const SizedBox(height: 2),
                  Text(
                    'Discover classes and events for kids',
                    style: textStyles.bodySmall,
                  ),
                ],
              ),
            ),
          ),
          IconButton(
            onPressed: onAuthTap,
            icon: Icon(isSignedIn ? Icons.logout : Icons.person_outline),
          ),
        ],
      ),
    );
  }
}

/// Extracted search bar widget.
class _SearchBar extends ConsumerWidget {
  const _SearchBar({
    required this.controller,
    required this.onSearch,
  });

  final TextEditingController controller;
  final VoidCallback onSearch;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final searchTokens = ref.watch(
      componentTokensProvider.select((t) => t.searchBar),
    );
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));

    // Cache border radius
    final borderRadius = BorderRadius.circular(searchTokens.borderRadius);

    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: spacing.md,
        vertical: spacing.sm,
      ),
      child: SizedBox(
        height: searchTokens.height,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: searchTokens.background,
            borderRadius: borderRadius,
            border: Border.all(color: searchTokens.border),
          ),
          child: TextField(
            controller: controller,
            decoration: InputDecoration(
              hintText: 'Search activities, organizations...',
              hintStyle: TextStyle(color: searchTokens.placeholder),
              prefixIcon: Icon(Icons.search, color: searchTokens.icon),
              suffixIcon: ValueListenableBuilder<TextEditingValue>(
                valueListenable: controller,
                builder: (context, value, _) {
                  if (value.text.isEmpty) return const SizedBox.shrink();
                  return IconButton(
                    onPressed: () {
                      controller.clear();
                      onSearch();
                    },
                    icon: Icon(Icons.clear, color: searchTokens.clearIcon),
                  );
                },
              ),
              border: InputBorder.none,
              contentPadding: EdgeInsets.symmetric(
                horizontal: searchTokens.padding,
                vertical: 12,
              ),
            ),
            onSubmitted: (_) => onSearch(),
            textInputAction: TextInputAction.search,
          ),
        ),
      ),
    );
  }
}

/// Extracted quick filters widget.
class _QuickFilters extends ConsumerWidget {
  const _QuickFilters({
    required this.onFilterBadgeTap,
    required this.onDayTap,
    required this.onAreaChanged,
    required this.onPricingTypeChanged,
    required this.onScheduleTypeChanged,
  });

  final VoidCallback onFilterBadgeTap;
  final ValueChanged<int> onDayTap;
  final ValueChanged<String?> onAreaChanged;
  final ValueChanged<String?> onPricingTypeChanged;
  final ValueChanged<String?> onScheduleTypeChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));
    final filters = ref.watch(activitiesFiltersProvider);

    return Padding(
      padding: EdgeInsets.only(bottom: spacing.sm),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          FilterChipBar(
            children: [
              FilterBadge(
                count: filters.activeFilterCount,
                onTap: onFilterBadgeTap,
              ),
              // Use const list generation for better performance
              for (int index = 0; index < 7; index++)
                TokenFilterChip(
                  label: AppConstants.daysOfWeekShort[index],
                  selected: filters.dayOfWeekUtc == index,
                  onSelected: (_) => onDayTap(index),
                ),
            ],
          ),
          SizedBox(height: spacing.sm),
          AreaFilterChips(
            selectedAreaId: filters.areaId,
            onAreaChanged: onAreaChanged,
          ),
          SizedBox(height: spacing.sm),
          FilterChipBar(
            children: [
              DropdownFilterChip(
                label: 'Pricing',
                value: filters.pricingType?.toApiString(),
                options: AppConstants.pricingTypes.keys.toList(),
                displayNameBuilder: AppConstants.getPricingTypeName,
                onChanged: onPricingTypeChanged,
              ),
              DropdownFilterChip(
                label: 'Schedule',
                value: filters.scheduleType?.toApiString(),
                options: AppConstants.scheduleTypes.keys.toList(),
                displayNameBuilder: AppConstants.getScheduleTypeName,
                onChanged: onScheduleTypeChanged,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Extracted results list widget.
class _ResultsList extends ConsumerWidget {
  const _ResultsList({
    required this.scrollController,
    required this.onRefresh,
    required this.onClearFilters,
  });

  final ScrollController scrollController;
  final VoidCallback onRefresh;
  final VoidCallback onClearFilters;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(activitiesViewModelProvider);
    final colors = ref.watch(semanticTokensProvider.select((s) => s.color));
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));

    if (state.isLoading && state.items.isEmpty) {
      return Center(
        child: CircularProgressIndicator(color: colors.primary),
      );
    }

    if (state.errorMessage != null && state.items.isEmpty) {
      return _ErrorState(
        message: state.errorMessage!,
        onRetry: onRefresh,
      );
    }

    if (state.items.isEmpty) {
      return _EmptyState(onClearFilters: onClearFilters);
    }

    return RefreshIndicator(
      onRefresh: () async {
        onRefresh();
        await Future.delayed(const Duration(milliseconds: 500));
      },
      child: ListView.builder(
        controller: scrollController,
        padding: EdgeInsets.only(top: spacing.sm),
        // Pre-build items off-screen for smoother scrolling.
        scrollCacheExtent: const ScrollCacheExtent.pixels(200),
        itemCount: state.items.length + (state.hasMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index >= state.items.length) {
            return _LoadMoreIndicator(isLoading: state.isLoadingMore);
          }
          final result = state.items[index];
          return ActivityCard(
            key: ValueKey(result.id),
            result: result,
            onTap: () => _navigateToDetail(context, result),
            onOrganizationTap: () => _navigateToOrg(context, result),
          );
        },
      ),
    );
  }

  void _navigateToDetail(BuildContext context, ActivitySearchResultEntity result) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ActivityDetailScreen(result: result),
      ),
    );
  }

  void _navigateToOrg(BuildContext context, ActivitySearchResultEntity result) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => OrganizationScreen(organization: result.organization),
      ),
    );
  }
}

/// Load more indicator.
class _LoadMoreIndicator extends ConsumerWidget {
  const _LoadMoreIndicator({required this.isLoading});

  final bool isLoading;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));
    final colors = ref.watch(semanticTokensProvider.select((s) => s.color));

    return Padding(
      padding: EdgeInsets.all(spacing.md),
      child: Center(
        child: isLoading
            ? CircularProgressIndicator(color: colors.primary)
            : const Text('Scroll for more'),
      ),
    );
  }
}

/// Empty state widget.
class _EmptyState extends ConsumerWidget {
  const _EmptyState({required this.onClearFilters});

  final VoidCallback onClearFilters;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));
    final colors = ref.watch(semanticTokensProvider.select((s) => s.color));
    final textStyles = ref.watch(semanticTokensProvider.select((s) => s.text));

    return Center(
      child: Padding(
        padding: EdgeInsets.all(spacing.xl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.search_off,
              size: 64,
              color: colors.textTertiary.withValues(alpha: 0.5),
            ),
            SizedBox(height: spacing.md),
            Text('No activities found', style: textStyles.titleMedium),
            SizedBox(height: spacing.sm),
            Text(
              'Try adjusting your filters or search terms',
              style: textStyles.bodySmall,
              textAlign: TextAlign.center,
            ),
            SizedBox(height: spacing.lg),
            OutlinedButton(
              onPressed: onClearFilters,
              child: const Text('Clear filters'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Error state widget.
class _ErrorState extends ConsumerWidget {
  const _ErrorState({
    required this.message,
    required this.onRetry,
  });

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));
    final colors = ref.watch(semanticTokensProvider.select((s) => s.color));
    final textStyles = ref.watch(semanticTokensProvider.select((s) => s.text));

    return Center(
      child: Padding(
        padding: EdgeInsets.all(spacing.xl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 64,
              color: colors.error.withValues(alpha: 0.7),
            ),
            SizedBox(height: spacing.md),
            Text('Something went wrong', style: textStyles.titleMedium),
            SizedBox(height: spacing.sm),
            Text(
              message,
              style: textStyles.caption,
              textAlign: TextAlign.center,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            SizedBox(height: spacing.lg),
            ElevatedButton(
              onPressed: onRetry,
              child: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}
