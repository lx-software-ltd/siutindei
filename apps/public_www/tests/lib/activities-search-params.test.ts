import { describe, expect, it } from 'vitest';

import {
  buildSearchQueryString,
  categoryIdsForTypes,
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
});
