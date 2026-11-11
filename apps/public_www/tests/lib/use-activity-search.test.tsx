import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DEFAULT_SEARCH_FILTERS } from '@/lib/activities/search-params';
import { useActivitySearch } from '@/lib/activities/search/use-activity-search';
import type { ActivityListing } from '@/lib/activities/types';

vi.mock('@/lib/activities/search-client', () => ({
  fetchActivitySearch: vi.fn(),
}));

import { fetchActivitySearch } from '@/lib/activities/search-client';

function listing(id: string): ActivityListing {
  return {
    activity: { id },
    location: { id: `loc-${id}` },
    pricing: null,
    schedule: null,
  } as ActivityListing;
}

describe('useActivitySearch', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('ignores a load-more response after the filters change', async () => {
    let resolveMore: (value: {
      items: ActivityListing[];
      nextCursor: string | null;
      categoryMatch: 'exact';
    }) => void = () => undefined;
    vi.mocked(fetchActivitySearch).mockImplementation(async (params) => {
      if (params.cursor) {
        return new Promise((resolve) => {
          resolveMore = resolve;
        });
      }
      return {
        items: [listing('NEW-1')],
        nextCursor: 'cursor-1',
        categoryMatch: 'exact',
      };
    });

    const { result, rerender } = renderHook(
      ({ textQuery }: { textQuery: string }) =>
        useActivitySearch({
          filters: { ...DEFAULT_SEARCH_FILTERS, textQuery },
          locale: 'en',
          pageSize: 30,
        }),
      { initialProps: { textQuery: '' } },
    );

    await waitFor(() => {
      expect(result.current.items.map((item) => item.activity.id)).toEqual([
        'NEW-1',
      ]);
    });

    act(() => {
      result.current.loadMore();
    });
    rerender({ textQuery: 'paint' });

    await act(async () => {
      resolveMore({
        items: [listing('OLD-2')],
        nextCursor: 'stale',
        categoryMatch: 'exact',
      });
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.items.map((item) => item.activity.id)).toEqual([
      'NEW-1',
    ]);
  });
});
