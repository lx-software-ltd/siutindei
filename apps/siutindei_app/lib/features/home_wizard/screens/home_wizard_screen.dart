import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../config/tokens/tokens.dart';
import '../../../domain/entities/entities.dart';
import '../../activity_detail/screens/activity_detail_screen.dart';
import '../../organization/screens/organization_screen.dart';
import '../../search/widgets/activity_card.dart';
import '../home_wizard_viewmodel.dart';
import '../models/home_wizard_choices.dart';

/// Home screen with sequential wizard, summary chips, and search results.
class HomeWizardScreen extends ConsumerStatefulWidget {
  const HomeWizardScreen({super.key});

  @override
  ConsumerState<HomeWizardScreen> createState() => _HomeWizardScreenState();
}

class _HomeWizardScreenState extends ConsumerState<HomeWizardScreen> {
  final _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final wizardState = ref.watch(homeWizardViewModelProvider);
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));
    final textStyles = ref.watch(semanticTokensProvider.select((s) => s.text));

    if (wizardState.isLoadingChoices) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    if (wizardState.choices == null) {
      return Scaffold(
        body: Center(
          child: Text(
            wizardState.errorMessage ?? 'Unable to load choices.',
            style: textStyles.bodyMedium,
          ),
        ),
      );
    }

    return Scaffold(
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: EdgeInsets.fromLTRB(
                spacing.md,
                spacing.md,
                spacing.md,
                spacing.sm,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Siu Tin Dei', style: textStyles.headlineMedium),
                  SizedBox(height: spacing.sm),
                  _WizardSummaryBar(
                    choices: wizardState.choices!,
                    state: wizardState,
                  ),
                ],
              ),
            ),
            if (wizardState.currentStep != HomeWizardStep.results)
              Expanded(
                child: _WizardStepContent(
                  choices: wizardState.choices!,
                  state: wizardState,
                ),
              )
            else ...[
              Padding(
                padding: EdgeInsets.symmetric(horizontal: spacing.md),
                child: TextField(
                  controller: _searchController,
                  decoration: const InputDecoration(
                    hintText: 'Search activities, organizations...',
                    prefixIcon: Icon(Icons.search),
                  ),
                  onChanged: (value) {
                    ref
                        .read(homeWizardViewModelProvider.notifier)
                        .updateSearchQuery(value);
                  },
                ),
              ),
              SizedBox(height: spacing.sm),
              Expanded(child: _WizardResultsList(state: wizardState)),
            ],
          ],
        ),
      ),
    );
  }
}

class _WizardSummaryBar extends ConsumerWidget {
  const _WizardSummaryBar({required this.choices, required this.state});

  final HomeWizardChoices choices;
  final HomeWizardState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));
    final notifier = ref.read(homeWizardViewModelProvider.notifier);

    final activityLabel = _activitySummaryLabel();
    final ageLabel = _ageSummaryLabel();
    final regionLabel = _regionSummaryLabel();

    return Wrap(
      spacing: spacing.sm,
      runSpacing: spacing.sm,
      children: [
        if (activityLabel != null)
          ActionChip(
            label: Text(activityLabel),
            onPressed: () => notifier.goToStep(HomeWizardStep.activityTypes),
          ),
        if (ageLabel != null)
          ActionChip(
            label: Text(ageLabel),
            onPressed: () => notifier.goToStep(HomeWizardStep.ageGroup),
          ),
        if (regionLabel != null)
          ActionChip(
            label: Text(regionLabel),
            onPressed: () => notifier.goToStep(HomeWizardStep.neighbourhood),
          ),
      ],
    );
  }

  String? _activitySummaryLabel() {
    if (state.selectedActivityTypeIds.isEmpty) {
      return null;
    }
    final labels = choices.activityTypes
        .where((type) => state.selectedActivityTypeIds.contains(type.id))
        .map((type) => type.labels.en)
        .toList();
    return labels.join(', ');
  }

  String? _ageSummaryLabel() {
    final ageGroupId = state.selectedAgeGroupId;
    if (ageGroupId == null) {
      return null;
    }
    return choices.ageGroups
        .firstWhere((group) => group.id == ageGroupId)
        .labels
        .en;
  }

  String? _regionSummaryLabel() {
    final regionId = state.selectedRegionId;
    if (regionId == null) {
      return null;
    }
    final region = choices.regions
        .firstWhere((item) => item.id == regionId)
        .labels
        .en;
    final neighbourhoodId = state.selectedNeighbourhoodId;
    if (neighbourhoodId == null) {
      return region;
    }
    for (final item in choices.neighbourhoods) {
      if (item.id == neighbourhoodId) {
        return item.labels.en;
      }
    }
    return region;
  }
}

class _WizardStepContent extends ConsumerWidget {
  const _WizardStepContent({required this.choices, required this.state});

  final HomeWizardChoices choices;
  final HomeWizardState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));
    final textStyles = ref.watch(semanticTokensProvider.select((s) => s.text));
    final notifier = ref.read(homeWizardViewModelProvider.notifier);

    switch (state.currentStep) {
      case HomeWizardStep.activityTypes:
        return ListView(
          padding: EdgeInsets.all(spacing.md),
          children: [
            Text(
              'What activities are you looking for?',
              style: textStyles.titleMedium,
            ),
            SizedBox(height: spacing.md),
            for (final option in choices.activityTypes)
              _WizardOptionTile(
                label: option.labels.en,
                selected: state.selectedActivityTypeIds.contains(option.id),
                onTap: () => notifier.toggleActivityType(option.id),
              ),
            SizedBox(height: spacing.md),
            FilledButton(
              onPressed: state.selectedActivityTypeIds.isEmpty
                  ? null
                  : notifier.confirmActivityTypes,
              child: const Text('Continue'),
            ),
          ],
        );
      case HomeWizardStep.ageGroup:
        return ListView(
          padding: EdgeInsets.all(spacing.md),
          children: [
            Text('How old is your child?', style: textStyles.titleMedium),
            SizedBox(height: spacing.md),
            for (final option in choices.ageGroups)
              _WizardOptionTile(
                label: option.labels.en,
                selected: state.selectedAgeGroupId == option.id,
                onTap: () => notifier.selectAgeGroup(option.id),
              ),
          ],
        );
      case HomeWizardStep.region:
        return ListView(
          padding: EdgeInsets.all(spacing.md),
          children: [
            Text('Which area is near you?', style: textStyles.titleMedium),
            if (state.prefetchStatus == HomeWizardPrefetchStatus.loading)
              Padding(
                padding: EdgeInsets.only(top: spacing.md),
                child: const LinearProgressIndicator(),
              ),
            SizedBox(height: spacing.md),
            for (final option in choices.regions)
              _WizardOptionTile(
                label: option.labels.en,
                selected: state.selectedRegionId == option.id,
                onTap: () => notifier.selectRegion(option.id),
              ),
          ],
        );
      case HomeWizardStep.neighbourhood:
        final regionId = state.selectedRegionId;
        final options = choices.neighbourhoods
            .where((item) => item.regionId == regionId)
            .toList();
        return ListView(
          padding: EdgeInsets.all(spacing.md),
          children: [
            Text('Which neighbourhood?', style: textStyles.titleMedium),
            SizedBox(height: spacing.md),
            _WizardOptionTile(
              label: 'Anywhere in this area',
              selected: state.selectedNeighbourhoodId == null,
              onTap: () => notifier.selectNeighbourhood(null),
            ),
            for (final option in options)
              _WizardOptionTile(
                label: option.labels.en,
                selected: state.selectedNeighbourhoodId == option.id,
                onTap: () => notifier.selectNeighbourhood(option.id),
              ),
          ],
        );
      case HomeWizardStep.results:
        return const SizedBox.shrink();
    }
  }
}

class _WizardOptionTile extends StatelessWidget {
  const _WizardOptionTile({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        title: Text(label),
        trailing: selected ? const Icon(Icons.check_circle) : null,
        onTap: onTap,
      ),
    );
  }
}

class _WizardResultsList extends ConsumerWidget {
  const _WizardResultsList({required this.state});

  final HomeWizardState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final colors = ref.watch(semanticTokensProvider.select((s) => s.color));
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));
    final textStyles = ref.watch(semanticTokensProvider.select((s) => s.text));

    if (state.prefetchStatus == HomeWizardPrefetchStatus.loading) {
      return Center(child: CircularProgressIndicator(color: colors.primary));
    }

    if (state.prefetchStatus == HomeWizardPrefetchStatus.error) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              state.errorMessage ?? 'Something went wrong',
              style: textStyles.bodyMedium,
            ),
            SizedBox(height: spacing.md),
            ElevatedButton(
              onPressed: () {
                ref.read(homeWizardViewModelProvider.notifier).retryPrefetch();
              },
              child: const Text('Try again'),
            ),
          ],
        ),
      );
    }

    if (state.filteredResults.isEmpty) {
      return Center(
        child: Text(
          'No activities found. Try changing your choices.',
          style: textStyles.bodyMedium,
          textAlign: TextAlign.center,
        ),
      );
    }

    return ListView.builder(
      padding: EdgeInsets.only(top: spacing.sm),
      itemCount: state.filteredResults.length,
      itemBuilder: (context, index) {
        final result = state.filteredResults[index];
        return ActivityCard(
          key: ValueKey(result.id),
          result: result,
          onTap: () => _openDetail(context, result),
          onOrganizationTap: () => _openOrganization(context, result),
        );
      },
    );
  }

  void _openDetail(BuildContext context, ActivitySearchResultEntity result) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => ActivityDetailScreen(result: result)),
    );
  }

  void _openOrganization(
    BuildContext context,
    ActivitySearchResultEntity result,
  ) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => OrganizationScreen(organization: result.organization),
      ),
    );
  }
}
