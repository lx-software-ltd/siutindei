import type { Locale } from '@/content';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';

export type SearchViewMode = 'list' | 'map';

export interface SearchFiltersState {
  readonly ageGroupId: string | null;
  readonly regionId: string | null;
  readonly neighbourhoodId: string | null;
  readonly activityTypeIds: readonly string[];
  readonly textQuery: string;
}

export const DEFAULT_SEARCH_FILTERS: SearchFiltersState = {
  ageGroupId: homeWizardChoices.ageGroups[1]?.id ?? null,
  regionId: null,
  neighbourhoodId: null,
  activityTypeIds: [],
  textQuery: '',
};

export function placeLabelForFilters(
  filters: SearchFiltersState,
  locale: Locale,
): string | null {
  const neighbourhood = homeWizardChoices.neighbourhoods.find(
    (entry) =>
      entry.id === filters.neighbourhoodId && entry.regionId === filters.regionId,
  );
  if (neighbourhood) {
    return labelForLocale(neighbourhood.labels, locale);
  }
  const region = homeWizardChoices.regions.find(
    (entry) => entry.id === filters.regionId,
  );
  return region ? labelForLocale(region.labels, locale) : null;
}

export function searchAgeForGroup(ageGroupId: string | null): number | undefined {
  if (!ageGroupId) {
    return undefined;
  }
  const group = homeWizardChoices.ageGroups.find(
    (entry) => entry.id === ageGroupId,
  );
  return group?.searchAge;
}

export function areaIdForRegion(regionId: string | null): string | undefined {
  if (!regionId) {
    return undefined;
  }
  const region = homeWizardChoices.regions.find(
    (entry) => entry.id === regionId,
  );
  return region?.areaId;
}

export function areaIdForFilters(
  filters: SearchFiltersState,
): string | undefined {
  if (filters.neighbourhoodId) {
    const neighbourhood = homeWizardChoices.neighbourhoods.find(
      (entry) => entry.id === filters.neighbourhoodId,
    );
    if (neighbourhood && neighbourhood.regionId === filters.regionId) {
      return neighbourhood.areaId;
    }
  }
  return areaIdForRegion(filters.regionId);
}

export function toggleActivityTypeId(
  filters: SearchFiltersState,
  typeId: string,
): SearchFiltersState {
  const next = new Set(filters.activityTypeIds);
  if (next.has(typeId)) {
    next.delete(typeId);
  } else {
    next.add(typeId);
  }
  return {
    ...filters,
    activityTypeIds: [...next],
  };
}

export function categoryIdsForTypes(
  activityTypeIds: readonly string[],
): readonly string[] {
  const ids: string[] = [];
  for (const typeId of activityTypeIds) {
    const match = homeWizardChoices.activityTypes.find(
      (entry) => entry.id === typeId,
    );
    if (match?.categoryId) {
      ids.push(match.categoryId);
    }
  }
  return ids;
}

export function parseSearchFiltersFromQuery(
  searchParams: URLSearchParams,
): SearchFiltersState {
  const ageGroupId = searchParams.get('age') ?? DEFAULT_SEARCH_FILTERS.ageGroupId;
  const regionId = searchParams.get('region') || null;
  const neighbourhoodId = searchParams.get('neighbourhood') || null;
  const typesParam = searchParams.get('types');
  const activityTypeIds = typesParam
    ? typesParam.split(',').filter((value) => value.length > 0)
    : [];
  const textQuery = searchParams.get('q') ?? '';

  return {
    ageGroupId,
    regionId,
    neighbourhoodId,
    activityTypeIds,
    textQuery,
  };
}

export function parseSearchViewMode(
  searchParams: URLSearchParams,
): SearchViewMode {
  return searchParams.get('view') === 'list' ? 'list' : 'map';
}

export function buildSearchQueryString(
  filters: SearchFiltersState,
  options?: { readonly view?: SearchViewMode },
): string {
  const params = new URLSearchParams();
  if (filters.ageGroupId) {
    params.set('age', filters.ageGroupId);
  }
  if (filters.regionId) {
    params.set('region', filters.regionId);
  }
  if (filters.neighbourhoodId) {
    params.set('neighbourhood', filters.neighbourhoodId);
  }
  if (filters.activityTypeIds.length > 0) {
    params.set('types', filters.activityTypeIds.join(','));
  }
  if (filters.textQuery.trim()) {
    params.set('q', filters.textQuery.trim());
  }
  const view = options?.view ?? 'map';
  params.set('view', view);
  return params.toString();
}

export function filtersToApiParams(filters: SearchFiltersState): {
  readonly age?: number;
  readonly areaId?: string;
  readonly categoryIds: readonly string[];
} {
  return {
    age: searchAgeForGroup(filters.ageGroupId),
    areaId: areaIdForFilters(filters),
    categoryIds: categoryIdsForTypes(filters.activityTypeIds),
  };
}
