import type { Locale } from '@/content/locales';
import {
  DEFAULT_SEARCH_KINDS,
  homeWizardChoices,
  kindOption,
  labelForLocale,
} from '@/lib/home-wizard/choices';

import { comingWeekend, hongKongToday } from './schedule-dates';
import type { ActivitySearchParams, ActivitySearchSort } from './types';

export type SearchViewMode = 'list' | 'map';

export type SearchDayChoice = 'weekend' | 'weekdays' | `${number}`;

export interface SearchFiltersState {
  /** One offered kind, or none for the default mix of kinds. */
  readonly kind?: string | null;
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

export function ageRangeForGroup(
  ageGroupId: string | null,
): { readonly ageMin: number; readonly ageMax: number } | undefined {
  if (!ageGroupId) {
    return undefined;
  }
  const group = homeWizardChoices.ageGroups.find(
    (entry) => entry.id === ageGroupId,
  );
  return group ? { ageMin: group.minAge, ageMax: group.maxAge } : undefined;
}

/** The sample age analytics records for an age group. */
export function searchAgeForGroup(ageGroupId: string | null): number | undefined {
  return homeWizardChoices.ageGroups.find((entry) => entry.id === ageGroupId)
    ?.searchAge;
}

/** Topics apply to the default mix and to kinds that have them. */
export function kindHasTopics(kind: string | null | undefined): boolean {
  return kind ? kindOption(kind)?.hasTopics === true : true;
}

/** Class-price and free-trial filters only make sense for classes. */
export function kindHasClassFilters(kind: string | null | undefined): boolean {
  return !kind || kind === 'class';
}

export function withKind(
  filters: SearchFiltersState,
  kind: string | null,
): SearchFiltersState {
  const next: SearchFiltersState = { ...filters, kind };
  return {
    ...next,
    activityTypeIds: kindHasTopics(kind) ? next.activityTypeIds : [],
    ...(kindHasClassFilters(kind) ? {} : { classPriceMax: null, freeTrial: false }),
  };
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
function parseKind(value: string | null): string | null {
  return kindOption(value) ? value : null;
}

function parseAgeGroupId(value: string | null): string | null {
  return homeWizardChoices.ageGroups.some((group) => group.id === value)
    ? value
    : null;
}

function parseActivityTypeIds(value: string | null): string[] {
  if (!value) {
    return [];
  }
  const known = new Set(homeWizardChoices.activityTypes.map((type) => type.id));
  return value.split(',').filter((typeId) => known.has(typeId));
}

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
  const kind = parseKind(searchParams.get('kind'));
  const ageGroupId = parseAgeGroupId(searchParams.get('age'));
  const regionId = searchParams.get('region') || null;
  const neighbourhoodId = searchParams.get('neighbourhood') || null;
  const activityTypeIds = kindHasTopics(kind)
    ? parseActivityTypeIds(searchParams.get('types'))
    : [];
  const classFilters = kindHasClassFilters(kind);
  const textQuery = searchParams.get('q') ?? '';

  const sort = searchParams.get('sort') === 'price' ? 'price' : undefined;
  return {
    ...(kind ? { kind } : {}),
    ageGroupId,
    regionId,
    neighbourhoodId,
    activityTypeIds,
    textQuery,
    ...(isOn(searchParams.get('free')) ? { free: true } : {}),
    ...(classFilters && isOn(searchParams.get('trial')) ? { freeTrial: true } : {}),
    ...withValue('day', parseDayChoice(searchParams.get('day'))),
    ...withValue('language', parseLanguage(searchParams.get('lang'))),
    ...withValue(
      'classPriceMax',
      classFilters ? parsePriceBand(searchParams.get('price')) : null,
    ),
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
  if (filters.kind) {
    params.set('kind', filters.kind);
  }
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

/** The map's family-food layer: places to eat in the same area, nothing else narrowed. */
export function familyFoodFilters(filters: SearchFiltersState): SearchFiltersState {
  return {
    ...DEFAULT_SEARCH_FILTERS,
    kind: 'eat',
    regionId: filters.regionId,
    neighbourhoodId: filters.neighbourhoodId,
  };
}

/** The weekend preset is not a kind: the default kinds on a Saturday or Sunday. */
export function isWeekendPreset(filters: SearchFiltersState): boolean {
  return !filters.kind && filters.day === 'weekend';
}

/** The weekend preset also limits dated sessions to the coming weekend. */
export function filtersToApiParams(
  filters: SearchFiltersState,
  today: string = hongKongToday(),
): Pick<
  ActivitySearchParams,
  | 'kinds'
  | 'ageMin'
  | 'ageMax'
  | 'areaId'
  | 'categoryIds'
  | 'q'
  | 'pricingType'
  | 'freeTrial'
  | 'daysOfWeekHkt'
  | 'dateFrom'
  | 'dateTo'
  | 'languages'
  | 'classPriceMax'
  | 'sort'
> & { readonly categoryIds: readonly string[] } {
  const textQuery = filters.textQuery.trim();
  const weekend = isWeekendPreset(filters) ? comingWeekend(today) : null;
  const days = daysForChoice(filters.day);
  const classFilters = kindHasClassFilters(filters.kind);
  return {
    kinds: filters.kind ? [filters.kind] : DEFAULT_SEARCH_KINDS,
    ...ageRangeForGroup(filters.ageGroupId),
    areaId: areaIdForFilters(filters),
    categoryIds: kindHasTopics(filters.kind)
      ? categoryIdsForTypes(filters.activityTypeIds)
      : [],
    ...(textQuery.length >= 2 ? { q: textQuery } : {}),
    ...(filters.free ? { pricingType: 'free' } : {}),
    ...(classFilters && filters.freeTrial ? { freeTrial: true } : {}),
    ...(days.length > 0 ? { daysOfWeekHkt: days } : {}),
    ...(weekend ?? {}),
    ...(filters.language ? { languages: [filters.language] } : {}),
    ...(classFilters &&
    filters.classPriceMax !== null &&
    filters.classPriceMax !== undefined
      ? { classPriceMax: filters.classPriceMax }
      : {}),
    ...(filters.sort === 'price' ? { sort: 'price' as const } : {}),
  };
}
