import {
  placeLabelForFilters,
  type SearchFiltersState,
} from '@/lib/activities/search-params';
import { formatContentTemplate } from '@/content/content-field-utils';
import type { Locale } from '@/content/locales';
import { getSearchConfig } from '@/lib/site-config';

import {
  homeWizardChoices,
  labelForLocale,
  neighbourhoodsForRegion,
  REGIONS_BY_ID,
  type WizardNeighbourhoodOption,
} from './choices';

export interface SearchAreaScope {
  readonly restricted: boolean;
  readonly areaIds: ReadonlySet<string>;
  readonly unknownTokens: readonly string[];
}

function scopeToken(value: string): string {
  return value.trim().toLowerCase();
}

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function neighbourhoodsForToken(
  token: string,
): readonly WizardNeighbourhoodOption[] | null {
  const key = scopeToken(token);
  if (key === '') {
    return null;
  }
  const region = homeWizardChoices.regions.find((entry) => entry.id === key);
  if (region) {
    return homeWizardChoices.neighbourhoods.filter(
      (entry) => entry.regionId === region.id,
    );
  }
  const district = homeWizardChoices.neighbourhoods.filter(
    (entry) => slug(entry.district) === key,
  );
  if (district.length > 0) {
    return district;
  }
  const neighbourhood = homeWizardChoices.neighbourhoods.find(
    (entry) => entry.id === key,
  );
  return neighbourhood ? [neighbourhood] : null;
}

export function resolveSearchAreaScope(raw: string | undefined): SearchAreaScope {
  const seen = new Set<string>();
  const tokens: string[] = [];
  for (const part of (raw ?? '').split(',')) {
    const token = scopeToken(part);
    if (token === '' || seen.has(token)) {
      continue;
    }
    seen.add(token);
    tokens.push(token);
  }
  if (tokens.length === 0) {
    return {
      restricted: false,
      areaIds: new Set<string>(),
      unknownTokens: [],
    };
  }
  const areaIds = new Set<string>();
  const unknownTokens: string[] = [];
  for (const token of tokens) {
    const matches = neighbourhoodsForToken(token);
    if (!matches) {
      unknownTokens.push(token);
      continue;
    }
    for (const match of matches) {
      areaIds.add(match.areaId);
    }
  }
  return {
    restricted: true,
    areaIds,
    unknownTokens,
  };
}

let cachedRaw: string | undefined;
let cachedScope: SearchAreaScope | undefined;

export function getConfiguredSearchAreaScope(): SearchAreaScope {
  const raw = getSearchConfig().searchAreaScope;
  if (cachedScope && cachedRaw === raw) {
    return cachedScope;
  }
  cachedRaw = raw;
  cachedScope = resolveSearchAreaScope(raw);
  return cachedScope;
}

export function clearSearchAreaScopeCacheForTests(): void {
  cachedRaw = undefined;
  cachedScope = undefined;
}

export function isRegionSelectable(regionId: string): boolean {
  const scope = getConfiguredSearchAreaScope();
  if (!scope.restricted) {
    return true;
  }
  return homeWizardChoices.neighbourhoods.some(
    (entry) => entry.regionId === regionId && scope.areaIds.has(entry.areaId),
  );
}

export function allowedNeighbourhoodsForRegion(
  regionId: string | null,
): readonly WizardNeighbourhoodOption[] {
  const matches = neighbourhoodsForRegion(regionId);
  const scope = getConfiguredSearchAreaScope();
  if (!scope.restricted) {
    return matches;
  }
  return matches.filter((entry) => scope.areaIds.has(entry.areaId));
}

export interface OpenRegion {
  readonly id: string;
  readonly neighbourhoods: readonly WizardNeighbourhoodOption[];
}

export function openRegions(): readonly OpenRegion[] {
  return homeWizardChoices.regions.flatMap((region) => {
    const neighbourhoods = allowedNeighbourhoodsForRegion(region.id);
    if (neighbourhoods.length === 0) {
      return [];
    }
    return [{ id: region.id, neighbourhoods }];
  });
}

/** "All areas" means the same thing as the only open region, so it is not a choice. */
export function isAllAreasSelectable(): boolean {
  const scope = getConfiguredSearchAreaScope();
  if (!scope.restricted) {
    return true;
  }
  return openRegions().length >= 2;
}

export function defaultOpenLocation(): {
  readonly regionId: string | null;
  readonly neighbourhoodId: string | null;
} {
  const regions = openRegions();
  if (!getConfiguredSearchAreaScope().restricted || regions.length !== 1) {
    return { regionId: null, neighbourhoodId: null };
  }
  const region = regions[0];
  return {
    regionId: region.id,
    neighbourhoodId:
      region.neighbourhoods.length === 1 ? region.neighbourhoods[0].id : null,
  };
}

/** Panel and wizard drafts show the only open place. Search URLs stay as written. */
export function withDefaultOpenLocation(
  filters: SearchFiltersState,
): SearchFiltersState {
  const scope = getConfiguredSearchAreaScope();
  if (!scope.restricted) {
    return filters;
  }
  if (!filters.regionId) {
    const fallback = defaultOpenLocation();
    if (!fallback.regionId) {
      return filters;
    }
    return { ...filters, ...fallback };
  }
  const allowed = allowedNeighbourhoodsForRegion(filters.regionId);
  if (allowed.length === 1 && filters.neighbourhoodId !== allowed[0].id) {
    return { ...filters, neighbourhoodId: allowed[0].id };
  }
  return filters;
}

/** The starting choice is not stored, so a wider scope later still applies. */
export function withoutImpliedOpenLocation(
  filters: SearchFiltersState,
): SearchFiltersState {
  const fallback = defaultOpenLocation();
  if (
    fallback.regionId &&
    filters.regionId === fallback.regionId &&
    filters.neighbourhoodId === fallback.neighbourhoodId
  ) {
    return { ...filters, regionId: null, neighbourhoodId: null };
  }
  return filters;
}

export function showsNeighbourhoodChoices(regionId: string | null): boolean {
  const allowed = allowedNeighbourhoodsForRegion(regionId);
  if (allowed.length > 1) {
    return true;
  }
  return allowed.length === 1 && getConfiguredSearchAreaScope().restricted;
}

const NAMED_PLACE_LIMIT = 3;

export type NamedOpenPlace =
  | { readonly kind: 'unrestricted' }
  | { readonly kind: 'none' }
  | { readonly kind: 'named'; readonly names: readonly string[] }
  | { readonly kind: 'generic' };

export interface PlaceListCopy {
  readonly comma: string;
  readonly pairTemplate: string;
  readonly finalTemplate: string;
}

export function joinPlaceNames(
  names: readonly string[],
  copy: PlaceListCopy,
): string {
  if (names.length <= 1) {
    return names[0] ?? '';
  }
  if (names.length === 2) {
    return formatContentTemplate(copy.pairTemplate, {
      first: names[0],
      second: names[1],
    });
  }
  return formatContentTemplate(copy.finalTemplate, {
    list: names.slice(0, -1).join(copy.comma),
    last: names[names.length - 1] ?? '',
  });
}

function regionIsFullyOpen(regionId: string): boolean {
  const allowed = allowedNeighbourhoodsForRegion(regionId);
  return (
    allowed.length > 0 &&
    allowed.length === neighbourhoodsForRegion(regionId).length
  );
}

function labelsForRegion(region: OpenRegion, locale: Locale): readonly string[] {
  if (regionIsFullyOpen(region.id)) {
    const option = REGIONS_BY_ID.get(region.id);
    return option ? [labelForLocale(option.labels, locale)] : [];
  }
  return region.neighbourhoods.map((entry) => labelForLocale(entry.labels, locale));
}

/** Names for the home popular heading. `none` means the scope matches nothing. */
export function namedOpenPlace(locale: Locale): NamedOpenPlace {
  const scope = getConfiguredSearchAreaScope();
  if (!scope.restricted) {
    return { kind: 'unrestricted' };
  }
  const regions = openRegions();
  if (regions.length === 0) {
    return { kind: 'none' };
  }
  const names = regions.flatMap((region) => labelsForRegion(region, locale));
  if (names.length === 0) {
    return { kind: 'none' };
  }
  if (names.length <= NAMED_PLACE_LIMIT) {
    return { kind: 'named', names };
  }
  return { kind: 'generic' };
}

/**
 * Names after "Activities in" for one region row.
 * More than three neighbourhoods keep the region name.
 */
export function namedOpenPlaceInRegion(
  regionId: string,
  locale: Locale,
): NamedOpenPlace {
  if (!getConfiguredSearchAreaScope().restricted || regionIsFullyOpen(regionId)) {
    return { kind: 'unrestricted' };
  }
  const names = allowedNeighbourhoodsForRegion(regionId).map((entry) =>
    labelForLocale(entry.labels, locale),
  );
  if (names.length === 0 || names.length > NAMED_PLACE_LIMIT) {
    return { kind: 'unrestricted' };
  }
  return { kind: 'named', names };
}

export function impliedOpenPlaceLabel(locale: string): string | null {
  const regions = openRegions();
  if (!getConfiguredSearchAreaScope().restricted || regions.length !== 1) {
    return null;
  }
  const region = regions[0];
  if (region.neighbourhoods.length === 1) {
    return labelForLocale(region.neighbourhoods[0].labels, locale);
  }
  const regionOption = REGIONS_BY_ID.get(region.id);
  return regionOption ? labelForLocale(regionOption.labels, locale) : null;
}

export function searchPlaceLabel(
  filters: SearchFiltersState,
  locale: Locale,
  labels: {
    readonly anywhere: string;
    readonly allAreas: string;
    readonly noAreas: string;
  },
): string {
  const selected = placeLabelForFilters(filters, locale);
  if (selected) {
    return selected;
  }
  const implied = impliedOpenPlaceLabel(locale);
  if (implied) {
    return implied;
  }
  if (!getConfiguredSearchAreaScope().restricted) {
    return labels.anywhere;
  }
  if (openRegions().length === 0) {
    return labels.noAreas;
  }
  return labels.allAreas;
}

export function sanitizeSearchFilters(filters: SearchFiltersState): {
  readonly filters: SearchFiltersState;
  readonly adjusted: boolean;
} {
  const scope = getConfiguredSearchAreaScope();
  if (!scope.restricted) {
    return { filters, adjusted: false };
  }
  let regionId = filters.regionId;
  let neighbourhoodId = filters.neighbourhoodId;
  let adjusted = false;
  if (regionId && !isRegionSelectable(regionId)) {
    const fallback = defaultOpenLocation();
    regionId = fallback.regionId;
    neighbourhoodId = fallback.neighbourhoodId;
    adjusted = true;
  }
  if (neighbourhoodId) {
    const allowed = allowedNeighbourhoodsForRegion(regionId);
    if (!allowed.some((entry) => entry.id === neighbourhoodId)) {
      neighbourhoodId = null;
      adjusted = true;
    }
  }
  if (!adjusted) {
    return { filters, adjusted: false };
  }
  return {
    filters: { ...filters, regionId, neighbourhoodId },
    adjusted: true,
  };
}

export function stagingScopeAreaIds(): ReadonlySet<string> | null {
  const scope = getConfiguredSearchAreaScope();
  if (!scope.restricted) {
    return null;
  }
  return scope.areaIds;
}
