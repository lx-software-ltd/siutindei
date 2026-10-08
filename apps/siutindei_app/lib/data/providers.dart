import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../domain/repositories/repositories.dart';
import '../domain/use_cases/use_cases.dart';
import '../services/service_providers.dart';
import 'repositories/activity_repository_impl.dart';

/// Provider for [ActivityRepository].
///
/// Provides the concrete implementation of the activity repository.
final activityRepositoryProvider = Provider<ActivityRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return ActivityRepositoryImpl(apiService);
});

/// Provider for [OrganizationRepository].
final organizationRepositoryProvider = Provider<OrganizationRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return OrganizationRepositoryImpl(apiService);
});

/// Provider for [SearchActivitiesUseCase].
final searchActivitiesUseCaseProvider = Provider<SearchActivitiesUseCase>((
  ref,
) {
  final repository = ref.watch(activityRepositoryProvider);
  return SearchActivitiesUseCase(repository);
});

/// Provider for [LoadMoreActivitiesUseCase].
final loadMoreActivitiesUseCaseProvider = Provider<LoadMoreActivitiesUseCase>((
  ref,
) {
  final repository = ref.watch(activityRepositoryProvider);
  return LoadMoreActivitiesUseCase(repository);
});

/// Provider for [GetActivityUseCase].
final getActivityUseCaseProvider = Provider<GetActivityUseCase>((ref) {
  final repository = ref.watch(activityRepositoryProvider);
  return GetActivityUseCase(repository);
});

/// Provider for [GetOrganizationUseCase].
final getOrganizationUseCaseProvider = Provider<GetOrganizationUseCase>((ref) {
  final repository = ref.watch(organizationRepositoryProvider);
  return GetOrganizationUseCase(repository);
});

/// Provider for [GetOrganizationActivitiesUseCase].
final getOrganizationActivitiesUseCaseProvider =
    Provider<GetOrganizationActivitiesUseCase>((ref) {
      final repository = ref.watch(organizationRepositoryProvider);
      return GetOrganizationActivitiesUseCase(repository);
    });
