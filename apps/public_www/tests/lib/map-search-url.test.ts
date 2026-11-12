import { describe, expect, it } from 'vitest';

import {
  buildMapSearchHref,
  buildSearchHref,
  regionIdForAreaId,
} from '@/lib/activities/map-search-url';
import { DEFAULT_SEARCH_FILTERS } from '@/lib/activities/search-params';

describe('buildMapSearchHref', () => {
  it('includes view=map in the search URL', () => {
    const href = buildMapSearchHref('en', {
      ...DEFAULT_SEARCH_FILTERS,
      regionId: 'kowloon',
    });

    expect(href).toBe('/en/search/?region=kowloon&view=map');
  });
});

describe('buildSearchHref', () => {
  it('builds a map-search URL from the current filters', () => {
    const href = buildSearchHref('en', {
      ...DEFAULT_SEARCH_FILTERS,
      regionId: 'kowloon',
    });

    expect(href).toBe('/en/search/?region=kowloon&view=map');
  });
});

describe('regionIdForAreaId', () => {
  it('maps a wizard area id back to the region id', () => {
    expect(regionIdForAreaId('a1111111-1111-1111-1111-111111111102')).toBe(
      'kowloon',
    );
  });
});
