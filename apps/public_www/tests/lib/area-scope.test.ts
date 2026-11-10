import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { afterEach, describe, expect, it } from 'vitest';

import { homeWizardChoices } from '@/lib/home-wizard/choices';
import {
  clearSearchAreaScopeCacheForTests,
  defaultOpenLocation,
  impliedOpenPlaceLabel,
  isAllAreasSelectable,
  namedOpenPlace,
  namedOpenPlaceInRegion,
  resolveSearchAreaScope,
  sanitizeSearchFilters,
  showsNeighbourhoodChoices,
  withoutImpliedOpenLocation,
} from '@/lib/home-wizard/area-scope';
import { DEFAULT_SEARCH_FILTERS } from '@/lib/activities/search-params';
import {
  loadRecentSearch,
  saveRecentSearch,
} from '@/lib/activities/recent-storage';

const kennedy = homeWizardChoices.neighbourhoods.find(
  (entry) => entry.id === 'central-and-western-kennedy-town',
);
const mongKok = homeWizardChoices.neighbourhoods.find(
  (entry) => entry.id === 'yau-tsim-mong-mong-kok',
);

describe('resolveSearchAreaScope', () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
    clearSearchAreaScopeCacheForTests();
    window.localStorage.clear();
  });

  it('stays unrestricted when the value is blank', () => {
    expect(resolveSearchAreaScope('  , ').restricted).toBe(false);
  });

  it('expands a region, a district, and a neighbourhood together', () => {
    expect(kennedy).toBeDefined();
    expect(mongKok).toBeDefined();
    const scope = resolveSearchAreaScope(
      ' Kowloon, central-and-western-kennedy-town, kowloon ',
    );
    const kowloonIds = homeWizardChoices.neighbourhoods
      .filter((entry) => entry.regionId === 'kowloon')
      .map((entry) => entry.areaId);
    expect([...scope.areaIds].sort()).toEqual(
      [...new Set([...kowloonIds, kennedy!.areaId])].sort(),
    );
    expect(scope.unknownTokens).toEqual([]);
    expect(scope.areaIds.has(mongKok!.areaId)).toBe(true);
  });

  it('treats islands as the region, which matches the district', () => {
    const region = resolveSearchAreaScope('islands');
    const districtIds = homeWizardChoices.neighbourhoods
      .filter((entry) => entry.district === 'Islands')
      .map((entry) => entry.areaId)
      .sort();
    expect([...region.areaIds].sort()).toEqual(districtIds);
    expect(districtIds.length).toBeGreaterThan(1);
  });

  it('keeps known slugs when one token is unknown', () => {
    const scope = resolveSearchAreaScope('kowloon,atlantis');
    expect(scope.restricted).toBe(true);
    expect(scope.unknownTokens).toEqual(['atlantis']);
    expect(scope.areaIds.size).toBeGreaterThan(0);
  });

  it('fails closed when every token is unknown', () => {
    const scope = resolveSearchAreaScope('atlantis,narnia');
    expect(scope.restricted).toBe(true);
    expect(scope.areaIds.size).toBe(0);
  });

  it('drops an out-of-scope deep link and a saved search', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'kowloon';
    clearSearchAreaScopeCacheForTests();
    const sanitized = sanitizeSearchFilters({
      ...DEFAULT_SEARCH_FILTERS,
      regionId: 'islands',
      neighbourhoodId: 'islands-lamma-island',
    });
    expect(sanitized.adjusted).toBe(true);
    expect(sanitized.filters.regionId).toBe('kowloon');
    expect(sanitized.filters.neighbourhoodId).toBeNull();

    saveRecentSearch({
      ...DEFAULT_SEARCH_FILTERS,
      regionId: 'islands',
      neighbourhoodId: null,
    });
    expect(loadRecentSearch()?.regionId).toBe('kowloon');
  });

  it('keeps a search with no area as written', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    const sanitized = sanitizeSearchFilters(DEFAULT_SEARCH_FILTERS);
    expect(sanitized.adjusted).toBe(false);
    expect(sanitized.filters.regionId).toBeNull();
  });

  it('describes one open region, several, and none', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    expect(isAllAreasSelectable()).toBe(false);
    expect(defaultOpenLocation()).toEqual({
      regionId: 'hong_kong_island',
      neighbourhoodId: 'southern-stanley',
    });
    expect(impliedOpenPlaceLabel('en')).toBe('Stanley');
    expect(showsNeighbourhoodChoices('hong_kong_island')).toBe(true);

    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern';
    clearSearchAreaScopeCacheForTests();
    expect(defaultOpenLocation().regionId).toBe('hong_kong_island');
    expect(defaultOpenLocation().neighbourhoodId).toBeNull();
    expect(impliedOpenPlaceLabel('en')).toBe('Hong Kong Island');

    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'kowloon,islands';
    clearSearchAreaScopeCacheForTests();
    expect(isAllAreasSelectable()).toBe(true);
    expect(defaultOpenLocation()).toEqual({
      regionId: null,
      neighbourhoodId: null,
    });
    expect(impliedOpenPlaceLabel('en')).toBeNull();

    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'atlantis';
    clearSearchAreaScopeCacheForTests();
    expect(isAllAreasSelectable()).toBe(false);
    expect(defaultOpenLocation().regionId).toBeNull();
    expect(impliedOpenPlaceLabel('en')).toBeNull();

    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
    clearSearchAreaScopeCacheForTests();
    expect(isAllAreasSelectable()).toBe(true);
    expect(showsNeighbourhoodChoices('islands')).toBe(true);
  });

  it('names the open place for the home heading', () => {
    expect(namedOpenPlace('en')).toEqual({ kind: 'unrestricted' });

    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    expect(namedOpenPlace('en')).toEqual({ kind: 'named', place: 'Stanley' });
    expect(namedOpenPlace('zh-HK')).toEqual({ kind: 'named', place: '赤柱' });

    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE =
      'southern-stanley,central-and-western-kennedy-town';
    clearSearchAreaScopeCacheForTests();
    expect(namedOpenPlace('en')).toEqual({
      kind: 'named',
      place: 'Kennedy Town and Stanley',
    });

    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'kowloon,islands';
    clearSearchAreaScopeCacheForTests();
    expect(namedOpenPlace('en')).toEqual({
      kind: 'named',
      place: 'Kowloon and Islands',
    });
    expect(namedOpenPlaceInRegion('kowloon', 'en')).toEqual({
      kind: 'unrestricted',
    });

    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'yau-tsim-mong';
    clearSearchAreaScopeCacheForTests();
    expect(namedOpenPlace('en')).toEqual({ kind: 'generic' });
    expect(namedOpenPlaceInRegion('kowloon', 'en')).toEqual({ kind: 'generic' });

    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'atlantis';
    clearSearchAreaScopeCacheForTests();
    expect(namedOpenPlace('en')).toEqual({ kind: 'none' });
  });

  it('drops the starting choice and keeps a chosen neighbourhood', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    expect(
      withoutImpliedOpenLocation({
        ...DEFAULT_SEARCH_FILTERS,
        regionId: 'hong_kong_island',
        neighbourhoodId: 'southern-stanley',
      }),
    ).toMatchObject({ regionId: null, neighbourhoodId: null });

    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'yau-tsim-mong';
    clearSearchAreaScopeCacheForTests();
    expect(
      withoutImpliedOpenLocation({
        ...DEFAULT_SEARCH_FILTERS,
        regionId: 'kowloon',
        neighbourhoodId: null,
      }).regionId,
    ).toBeNull();
    expect(
      withoutImpliedOpenLocation({
        ...DEFAULT_SEARCH_FILTERS,
        regionId: 'kowloon',
        neighbourhoodId: 'yau-tsim-mong-mong-kok',
      }).neighbourhoodId,
    ).toBe('yau-tsim-mong-mong-kok');
  });

  it('expands the same slugs as the backend', () => {
    const repoRoot = path.resolve(
      path.dirname(fileURLToPath(import.meta.url)),
      '../../../..',
    );
    const script = [
      'import json, sys',
      'sys.path.insert(0, "backend/src")',
      'from app.data.hk_neighbourhoods import resolve_search_area_scope',
      'tokens = [',
      '    "kowloon",',
      '    "yau-tsim-mong",',
      '    "central-and-western-kennedy-town",',
      '    "islands",',
      '    "hong_kong_island",',
      '    " Kowloon, atlantis ",',
      ']',
      'out = {}',
      'for raw in tokens:',
      '    ids, unknown = resolve_search_area_scope(raw)',
      '    out[raw] = {',
      '        "ids": None if ids is None else sorted(str(item) for item in ids),',
      '        "unknown": list(unknown),',
      '    }',
      'print(json.dumps(out))',
    ].join('\n');
    const backend = JSON.parse(
      execFileSync('python3', ['-c', script], {
        cwd: repoRoot,
        encoding: 'utf8',
      }),
    ) as Record<string, { ids: string[] | null; unknown: string[] }>;

    for (const [token, expected] of Object.entries(backend)) {
      const resolved = resolveSearchAreaScope(token);
      expect(resolved.unknownTokens).toEqual(expected.unknown);
      if (expected.ids === null) {
        expect(resolved.restricted).toBe(false);
      } else {
        expect([...resolved.areaIds].sort()).toEqual(expected.ids);
      }
    }
  });
});
