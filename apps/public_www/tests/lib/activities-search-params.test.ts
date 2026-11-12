import { describe, expect, it } from 'vitest';

import {
  activeRefinementCount,
  buildSearchQueryString,
  categoryIdsForTypes,
  daysForChoice,
  filtersToApiParams,
  parseSearchFiltersFromQuery,
  parseSearchViewMode,
  toggleActivityTypeId,
} from '@/lib/activities/search-params';

describe('search-params', () => {
  it('round-trips filters in the query string', () => {
    const params = new URLSearchParams(
      buildSearchQueryString({
        ageGroupId: '3-6',
        regionId: 'kowloon',
        neighbourhoodId: null,
        activityTypeIds: ['early-years', 'learning'],
        textQuery: 'music',
      }),
    );

    const parsed = parseSearchFiltersFromQuery(params);
    expect(parsed.ageGroupId).toBe('3-6');
    expect(parsed.regionId).toBe('kowloon');
    expect(parsed.neighbourhoodId).toBeNull();
    expect(parsed.activityTypeIds).toEqual(['early-years', 'learning']);
    expect(parsed.textQuery).toBe('music');
    expect(params.get('view')).toBe('map');
  });

  it('defaults to map view unless the query asks for the list', () => {
    expect(parseSearchViewMode(new URLSearchParams())).toBe('map');
    expect(parseSearchViewMode(new URLSearchParams('view=map'))).toBe('map');
    expect(parseSearchViewMode(new URLSearchParams('view=list'))).toBe(
      'list',
    );
  });

  it('writes view=list when the list is requested', () => {
    const query = buildSearchQueryString(
      {
        ageGroupId: '3-6',
        regionId: null,
        neighbourhoodId: null,
        activityTypeIds: [],
        textQuery: '',
      },
      { view: 'list' },
    );
    expect(new URLSearchParams(query).get('view')).toBe('list');
  });

  it('maps activity types to category ids', () => {
    expect(categoryIdsForTypes(['early-years'])).toEqual([
      'c1111111-1111-1111-1111-111111111201',
    ]);
  });

  it('toggles activity type ids without dropping other filters', () => {
    const base = {
      ageGroupId: '3-6',
      regionId: 'kowloon',
      neighbourhoodId: null,
      activityTypeIds: [] as const,
      textQuery: 'music',
    };

    const added = toggleActivityTypeId(base, 'early-years');
    expect(added.activityTypeIds).toEqual(['early-years']);
    expect(added.ageGroupId).toBe('3-6');
    expect(added.regionId).toBe('kowloon');
    expect(added.textQuery).toBe('music');

    const addedAgain = toggleActivityTypeId(added, 'learning');
    expect(addedAgain.activityTypeIds).toEqual(['early-years', 'learning']);

    const removed = toggleActivityTypeId(addedAgain, 'early-years');
    expect(removed.activityTypeIds).toEqual(['learning']);
  });

  it('round-trips refinements and maps them to API parameters', () => {
    const query = buildSearchQueryString(
      {
        ageGroupId: null,
        regionId: null,
        neighbourhoodId: null,
        activityTypeIds: [],
        textQuery: '',
        free: true,
        freeTrial: true,
        day: 'weekdays',
        language: 'yue',
        classPriceMax: 250,
        sort: 'price',
      },
      { view: 'list' },
    );
    expect(query).toBe('free=1&trial=1&day=weekdays&lang=yue&price=250&sort=price&view=list');

    const parsed = parseSearchFiltersFromQuery(new URLSearchParams(query));
    expect(activeRefinementCount(parsed)).toBe(5);
    expect(filtersToApiParams(parsed)).toMatchObject({
      pricingType: 'free',
      freeTrial: true,
      daysOfWeekHkt: [1, 2, 3, 4, 5],
      languages: ['yue'],
      classPriceMax: 250,
      sort: 'price',
    });
  });

  it('ignores unknown refinement values', () => {
    const parsed = parseSearchFiltersFromQuery(
      new URLSearchParams('day=9&lang=fr&price=abc&sort=name&free=no'),
    );
    expect(activeRefinementCount(parsed)).toBe(0);
    expect(parsed.sort).toBeUndefined();
    expect(daysForChoice('weekend')).toEqual([0, 6]);
    expect(daysForChoice('3')).toEqual([3]);
  });
});
