import { describe, expect, it } from 'vitest';

import {
  activeRefinementCount,
  ageRangeForGroup,
  buildSearchQueryString,
  categoryIdsForTypes,
  daysForChoice,
  filtersToApiParams,
  parseSearchFiltersFromQuery,
  parseSearchViewMode,
  toggleActivityTypeId,
  withKind,
  type SearchFiltersState,
} from '@/lib/activities/search-params';

const EMPTY: SearchFiltersState = {
  ageGroupId: null,
  regionId: null,
  neighbourhoodId: null,
  activityTypeIds: [],
  textQuery: '',
};

describe('search-params', () => {
  it('round-trips filters in the query string', () => {
    const params = new URLSearchParams(
      buildSearchQueryString({
        ageGroupId: '3-5',
        regionId: 'kowloon',
        neighbourhoodId: null,
        activityTypeIds: ['art', 'stem'],
        textQuery: 'music',
      }),
    );

    const parsed = parseSearchFiltersFromQuery(params);
    expect(parsed.ageGroupId).toBe('3-5');
    expect(parsed.regionId).toBe('kowloon');
    expect(parsed.neighbourhoodId).toBeNull();
    expect(parsed.activityTypeIds).toEqual(['art', 'stem']);
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
        ageGroupId: '3-5',
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
    expect(categoryIdsForTypes(['art'])).toEqual([
      'c1111111-1111-1111-1111-111111111304',
    ]);
  });

  it('toggles activity type ids without dropping other filters', () => {
    const base = {
      ageGroupId: '3-5',
      regionId: 'kowloon',
      neighbourhoodId: null,
      activityTypeIds: [] as const,
      textQuery: 'music',
    };

    const added = toggleActivityTypeId(base, 'art');
    expect(added.activityTypeIds).toEqual(['art']);
    expect(added.ageGroupId).toBe('3-5');
    expect(added.regionId).toBe('kowloon');
    expect(added.textQuery).toBe('music');

    const addedAgain = toggleActivityTypeId(added, 'stem');
    expect(addedAgain.activityTypeIds).toEqual(['art', 'stem']);

    const removed = toggleActivityTypeId(addedAgain, 'art');
    expect(removed.activityTypeIds).toEqual(['stem']);
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

  it('round-trips a kind and searches the default kinds without one', () => {
    const parsed = parseSearchFiltersFromQuery(
      new URLSearchParams(buildSearchQueryString(withKind(EMPTY, 'camp'))),
    );
    expect(parsed.kind).toBe('camp');
    expect(filtersToApiParams(parsed).kinds).toEqual(['camp']);
    expect(filtersToApiParams(EMPTY).kinds).toEqual(['class', 'camp', 'place']);
  });

  it('drops topics and class-only filters for a place', () => {
    const filters = withKind(
      {
        ...EMPTY,
        activityTypeIds: ['art'],
        freeTrial: true,
        classPriceMax: 250,
      },
      'place',
    );
    expect(filters.activityTypeIds).toEqual([]);
    expect(filters.freeTrial).toBe(false);
    expect(filters.classPriceMax).toBeNull();

    const parsed = parseSearchFiltersFromQuery(
      new URLSearchParams('kind=place&types=art&trial=1&price=250'),
    );
    expect(parsed.activityTypeIds).toEqual([]);
    expect(activeRefinementCount(parsed)).toBe(0);
    expect(filtersToApiParams(parsed)).toMatchObject({ categoryIds: [] });
    expect(filtersToApiParams(parsed)).not.toHaveProperty('freeTrial');
  });

  it('sends the age group as an age range', () => {
    expect(filtersToApiParams({ ...EMPTY, ageGroupId: '6-11' })).toMatchObject({
      ageMin: 6,
      ageMax: 11,
    });
    expect(ageRangeForGroup('0-1')).toEqual({ ageMin: 0, ageMax: 0 });
    expect(ageRangeForGroup('3-6')).toBeUndefined();
  });

  it('ignores unknown kinds, ages, and topics', () => {
    const parsed = parseSearchFiltersFromQuery(
      new URLSearchParams('kind=eat&age=3-6&types=early-years,art'),
    );
    expect(parsed.kind).toBeUndefined();
    expect(parsed.ageGroupId).toBeNull();
    expect(parsed.activityTypeIds).toEqual(['art']);
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
