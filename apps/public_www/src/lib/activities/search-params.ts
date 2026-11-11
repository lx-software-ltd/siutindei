import type { Locale } from '@/content/locales';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';

import type { ActivitySearchParams, ActivitySearchSort } from './types';

export type SearchViewMode = 'list' | 'map';

export type SearchDayChoice = 'weekend' | 'weekdays' | `${number}`;

export interface SearchFiltersState {
  readonly ageGroupId: string | null;
  readonly regionId: string | null;
  readonly neighbourhoodId: string | null;
  readonly activityTypeIds: readonly string[];
  readonly textQuery: string;
  /** Only free activities (`pricing_type=free`). */
  readonly free?: boolean;
  readonly freeTrial?: boolean;
  /** `weekend`, `weekdays`, or one Hong Kong day, `0` for Sunday. */
  readonly day?: SearchDayChoice | null;
  readonly language?: string | null;
  /** Highest price of one class in HKD. */
  readonly classPriceMax?: number | null;
  readonly sort?: ActivitySearchSort;
}

export const SEARCH_LANGUAGE_CODES = ['yue', 'en', 'zh'] as const;
export const SEARCH_PRICE_BANDS = [150, 250, 400] as const;
const WEEKDAYS = [1, 2, 3, 4, 5] as const;
const WEEKEND = [0, 6] as const;

export const DEFAULT_SEARCH_FILTERS: SearchFiltersState = {
  ageGroupId: null,
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

function areaIdForRegion(regionId: string | null): string | undefined {
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

export function daysForChoice(
  day: SearchDayChoice | null | undefined,
): readonly number[] {
  if (!day) {
    return [];
  }
  if (day === 'weekend') {
    return WEEKEND;
  }
  if (day === 'weekdays') {
    return WEEKDAYS;
  }
  const value = Number(day);
  return Number.isInteger(value) && value >= 0 && value <= 6 ? [value] : [];
}

function parseDayChoice(value: string | null): SearchDayChoice | null {
  if (value === 'weekend' || value === 'weekdays') {
    return value;
  }
  if (value !== null && /^[0-6]$/.test(value)) {
    return value as SearchDayChoice;
  }
  return null;
}

function parseLanguage(value: string | null): string | null {
  return value && (SEARCH_LANGUAGE_CODES as readonly string[]).includes(value)
    ? value
    : null;
}

function parsePriceBand(value: string | null): number | null {
  const parsed = value ? Number(value) : Number.NaN;
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function isOn(value: string | null): boolean {
  return value === '1' || value === 'true';
}

/** Number of refinements set beyond place, age, type, and text. */
export function activeRefinementCount(filters: SearchFiltersState): number {
  return [
    filters.free,
    filters.freeTrial,
    filters.day,
    filters.language,
    filters.classPriceMax !== null && filters.classPriceMax !== undefined,
  ].filter(Boolean).length;
}

export function parseSearchFiltersFromQuery(
  searchParams: URLSearchParams,
): SearchFiltersState {
  const ageGroupId = searchParams.get('age') || DEFAULT_SEARCH_FILTERS.ageGroupId;
  const regionId = searchParams.get('region') || null;
  const neighbourhoodId = searchParams.get('neighbourhood') || null;
  const typesParam = searchParams.get('types');
  const activityTypeIds = typesParam
    ? typesParam.split(',').filter((value) => value.length > 0)
    : [];
  const textQuery = searchParams.get('q') ?? '';

  const sort = searchParams.get('sort') === 'price' ? 'price' : undefined;
  return {
    ageGroupId,
    regionId,
    neighbourhoodId,
    activityTypeIds,
    textQuery,
    ...(isOn(searchParams.get('free')) ? { free: true } : {}),
    ...(isOn(searchParams.get('trial')) ? { freeTrial: true } : {}),
    ...withValue('day', parseDayChoice(searchParams.get('day'))),
    ...withValue('language', parseLanguage(searchParams.get('lang'))),
    ...withValue('classPriceMax', parsePriceBand(searchParams.get('price'))),
    ...(sort ? { sort } : {}),
  };
}

function withValue<Key extends string, Value>(
  key: Key,
  value: Value | null,
): { [K in Key]?: Value } {
  return value === null ? {} : ({ [key]: value } as { [K in Key]?: Value });
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
  if (filters.free) {
    params.set('free', '1');
  }
  if (filters.freeTrial) {
    params.set('trial', '1');
  }
  if (filters.day) {
    params.set('day', filters.day);
  }
  if (filters.language) {
    params.set('lang', filters.language);
  }
  if (filters.classPriceMax !== null && filters.classPriceMax !== undefined) {
    params.set('price', String(filters.classPriceMax));
  }
  if (filters.sort === 'price') {
    params.set('sort', 'price');
  }
  const view = options?.view ?? 'map';
  params.set('view', view);
  return params.toString();
}

export function filtersToApiParams(
  filters: SearchFiltersState,
): Pick<
  ActivitySearchParams,
  | 'age'
  | 'areaId'
  | 'categoryIds'
  | 'q'
  | 'pricingType'
  | 'freeTrial'
  | 'daysOfWeekHkt'
  | 'languages'
  | 'classPriceMax'
  | 'sort'
> & { readonly categoryIds: readonly string[] } {
  const textQuery = filters.textQuery.trim();
  const days = daysForChoice(filters.day);
  return {
    age: searchAgeForGroup(filters.ageGroupId),
    areaId: areaIdForFilters(filters),
    categoryIds: categoryIdsForTypes(filters.activityTypeIds),
    ...(textQuery.length >= 2 ? { q: textQuery } : {}),
    ...(filters.free ? { pricingType: 'free' } : {}),
    ...(filters.freeTrial ? { freeTrial: true } : {}),
    ...(days.length > 0 ? { daysOfWeekHkt: days } : {}),
    ...(filters.language ? { languages: [filters.language] } : {}),
    ...(filters.classPriceMax !== null && filters.classPriceMax !== undefined
      ? { classPriceMax: filters.classPriceMax }
      : {}),
    ...(filters.sort === 'price' ? { sort: 'price' as const } : {}),
  };
}
