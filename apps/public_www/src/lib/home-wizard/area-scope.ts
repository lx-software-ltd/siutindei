import type { SearchFiltersState } from '@/lib/activities/search-params';
import { getSearchConfig } from '@/lib/site-config';

import {
  homeWizardChoices,
  neighbourhoodsForRegion,
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
    regionId = null;
    neighbourhoodId = null;
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
