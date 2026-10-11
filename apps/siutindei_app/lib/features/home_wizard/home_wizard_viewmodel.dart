import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/core.dart';
import '../../data/providers.dart';
import '../../domain/entities/entities.dart';
import '../../domain/use_cases/use_cases.dart';
import 'models/home_wizard_choices.dart';

enum HomeWizardStep {
  activityTypes,
  ageGroup,
  region,
  neighbourhood,
  results,
}

enum HomeWizardPrefetchStatus { idle, loading, ready, error }

@immutable
class HomeWizardState {
  const HomeWizardState({
    this.choices,
    this.isLoadingChoices = true,
    this.currentStep = HomeWizardStep.activityTypes,
    this.selectedActivityTypeIds = const {},
    this.selectedAgeGroupId,
    this.selectedRegionId,
    this.selectedNeighbourhoodId,
    this.prefetchStatus = HomeWizardPrefetchStatus.idle,
    this.prefetchedResults = const [],
    this.filteredResults = const [],
    this.searchQuery = '',
    this.errorMessage,
  });

  final HomeWizardChoices? choices;
  final bool isLoadingChoices;
  final HomeWizardStep currentStep;
  final Set<String> selectedActivityTypeIds;
  final String? selectedAgeGroupId;
  final String? selectedRegionId;
  final String? selectedNeighbourhoodId;
  final HomeWizardPrefetchStatus prefetchStatus;
  final List<ActivitySearchResultEntity> prefetchedResults;
  final List<ActivitySearchResultEntity> filteredResults;
  final String searchQuery;
  final String? errorMessage;

  bool get isWizardComplete =>
      selectedActivityTypeIds.isNotEmpty &&
      selectedAgeGroupId != null &&
      selectedRegionId != null;

  HomeWizardState copyWith({
    HomeWizardChoices? choices,
    bool? isLoadingChoices,
    HomeWizardStep? currentStep,
    Set<String>? selectedActivityTypeIds,
    String? selectedAgeGroupId,
    String? selectedRegionId,
    String? selectedNeighbourhoodId,
    HomeWizardPrefetchStatus? prefetchStatus,
    List<ActivitySearchResultEntity>? prefetchedResults,
    List<ActivitySearchResultEntity>? filteredResults,
    String? searchQuery,
    String? errorMessage,
    bool clearError = false,
    bool clearAgeGroup = false,
    bool clearRegion = false,
    bool clearNeighbourhood = false,
  }) {
    return HomeWizardState(
      choices: choices ?? this.choices,
      isLoadingChoices: isLoadingChoices ?? this.isLoadingChoices,
      currentStep: currentStep ?? this.currentStep,
      selectedActivityTypeIds:
          selectedActivityTypeIds ?? this.selectedActivityTypeIds,
      selectedAgeGroupId: clearAgeGroup
          ? null
          : (selectedAgeGroupId ?? this.selectedAgeGroupId),
      selectedRegionId: clearRegion
          ? null
          : (selectedRegionId ?? this.selectedRegionId),
      selectedNeighbourhoodId: clearRegion || clearNeighbourhood
          ? null
          : (selectedNeighbourhoodId ?? this.selectedNeighbourhoodId),
      prefetchStatus: prefetchStatus ?? this.prefetchStatus,
      prefetchedResults: prefetchedResults ?? this.prefetchedResults,
      filteredResults: filteredResults ?? this.filteredResults,
      searchQuery: searchQuery ?? this.searchQuery,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class HomeWizardViewModel extends Notifier<HomeWizardState> {
  late final SearchActivitiesUseCase _searchUseCase;

  @override
  HomeWizardState build() {
    _searchUseCase = ref.watch(searchActivitiesUseCaseProvider);
    Future.microtask(_loadChoices);
    return const HomeWizardState();
  }

  Future<void> _loadChoices() async {
    try {
      final choices = await HomeWizardChoices.loadFromAsset();
      state = state.copyWith(choices: choices, isLoadingChoices: false);
    } on Exception {
      state = state.copyWith(
        isLoadingChoices: false,
        errorMessage: 'Unable to load activity choices.',
      );
    }
  }

  void toggleActivityType(String activityTypeId) {
    final updated = Set<String>.from(state.selectedActivityTypeIds);
    if (updated.contains(activityTypeId)) {
      updated.remove(activityTypeId);
    } else {
      updated.add(activityTypeId);
    }
    state = state.copyWith(
      selectedActivityTypeIds: updated,
      clearAgeGroup: true,
      clearRegion: true,
      prefetchStatus: HomeWizardPrefetchStatus.idle,
      prefetchedResults: const [],
      filteredResults: const [],
    );
  }

  void confirmActivityTypes() {
    if (state.selectedActivityTypeIds.isEmpty) {
      return;
    }
    state = state.copyWith(currentStep: HomeWizardStep.ageGroup);
  }

  Future<void> selectAgeGroup(String ageGroupId) async {
    state = state.copyWith(
      selectedAgeGroupId: ageGroupId,
      clearRegion: true,
      currentStep: HomeWizardStep.region,
      prefetchStatus: HomeWizardPrefetchStatus.loading,
      prefetchedResults: const [],
      filteredResults: const [],
      clearError: true,
    );
    await _prefetchResults();
  }

  void selectRegion(String regionId) {
    state = state.copyWith(
      selectedRegionId: regionId,
      clearNeighbourhood: true,
      currentStep: HomeWizardStep.neighbourhood,
    );
  }

  void selectNeighbourhood(String? neighbourhoodId) {
    state = state.copyWith(
      selectedNeighbourhoodId: neighbourhoodId,
      clearNeighbourhood: neighbourhoodId == null,
      currentStep: HomeWizardStep.results,
    );
    _applyRegionAndTextFilters();
  }

  void goToStep(HomeWizardStep step) {
    state = state.copyWith(currentStep: step);
    if (step == HomeWizardStep.activityTypes) {
      state = state.copyWith(
        clearAgeGroup: true,
        clearRegion: true,
        prefetchStatus: HomeWizardPrefetchStatus.idle,
        prefetchedResults: const [],
        filteredResults: const [],
      );
    } else if (step == HomeWizardStep.ageGroup) {
      state = state.copyWith(clearRegion: true, filteredResults: const []);
    } else if (step == HomeWizardStep.region) {
      state = state.copyWith(
        clearNeighbourhood: true,
        filteredResults: const [],
      );
    }
  }

  void updateSearchQuery(String query) {
    state = state.copyWith(searchQuery: query);
    _applyRegionAndTextFilters();
  }

  Future<void> retryPrefetch() async {
    state = state.copyWith(
      prefetchStatus: HomeWizardPrefetchStatus.loading,
      clearError: true,
    );
    await _prefetchResults();
  }

  Future<void> _prefetchResults() async {
    final choices = state.choices;
    final ageGroupId = state.selectedAgeGroupId;
    if (choices == null || ageGroupId == null) {
      return;
    }

    final ageGroup = choices.ageGroups.firstWhere(
      (group) => group.id == ageGroupId,
    );
    final categoryIds = choices.activityTypes
        .where((type) => state.selectedActivityTypeIds.contains(type.id))
        .map((type) => type.categoryId)
        .toList();

    final filters = SearchFilters(
      age: ageGroup.searchAge,
      categoryIds: categoryIds,
      limit: 200,
    );

    final result = await _searchUseCase.execute(filters);
    switch (result) {
      case Ok(value: final data):
        state = state.copyWith(
          prefetchStatus: HomeWizardPrefetchStatus.ready,
          prefetchedResults: data.items,
        );
        if (state.selectedRegionId != null) {
          _applyRegionAndTextFilters();
        }
      case Error():
        state = state.copyWith(
          prefetchStatus: HomeWizardPrefetchStatus.error,
          errorMessage: 'Unable to load activities. Pull to retry.',
        );
    }
  }

  void _applyRegionAndTextFilters() {
    final choices = state.choices;
    final regionId = state.selectedRegionId;
    if (choices == null || regionId == null) {
      return;
    }

    final region = choices.regions.firstWhere((item) => item.id == regionId);
    final neighbourhoodId = state.selectedNeighbourhoodId;
    String? neighbourhoodAreaId;
    if (neighbourhoodId != null) {
      for (final item in choices.neighbourhoods) {
        if (item.id == neighbourhoodId) {
          neighbourhoodAreaId = item.areaId;
        }
      }
    }
    final query = state.searchQuery.trim().toLowerCase();
    final filtered = state.prefetchedResults.where((result) {
      final matchesRegion = result.location.regionAreaId == region.areaId;
      if (!matchesRegion) {
        return false;
      }
      if (neighbourhoodAreaId != null &&
          result.location.areaId != neighbourhoodAreaId) {
        return false;
      }
      if (query.isEmpty) {
        return true;
      }
      final haystack = [
        result.activity.name,
        result.activity.description ?? '',
        result.organization.name,
      ].join(' ').toLowerCase();
      return haystack.contains(query);
    }).toList();

    state = state.copyWith(filteredResults: filtered);
  }
}

final homeWizardViewModelProvider =
    NotifierProvider<HomeWizardViewModel, HomeWizardState>(
      HomeWizardViewModel.new,
    );
