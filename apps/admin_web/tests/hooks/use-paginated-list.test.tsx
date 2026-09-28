import { act, renderHook, waitFor } from '@testing-library/react';
import type { InfiniteData } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';

import { useExhaustPages } from '@/hooks/use-exhaust-pages';
import { usePaginatedList, type PaginatedResponse } from '@/hooks/use-paginated-list';
import { getAdminQueryClient } from '@/lib/admin-query-client';

describe('usePaginatedList', () => {
  it('keeps loaded pages when a row is edited', async () => {
    const fetcher = vi.fn(async ({ cursor }: { cursor: string | null }) => {
      if (!cursor) {
        return { items: [{ id: 'a', name: 'A' }], nextCursor: 'p2', pendingCount: 3 };
      }
      return { items: [{ id: 'b', name: 'B' }], nextCursor: null, pendingCount: 3 };
    });
    const { result } = renderHook(() =>
      usePaginatedList<{ id: string; name: string }, Record<string, never>>({
        queryKey: ['pages-test'],
        defaultFilters: {},
        fetcher,
      })
    );

    await waitFor(() => expect(result.current.items.map((item) => item.id)).toEqual(['a']));
    expect(result.current.pendingCount).toBe(3);

    await act(async () => {
      await result.current.loadMore();
    });
    await waitFor(() => expect(result.current.items.map((item) => item.id)).toEqual(['a', 'b']));

    act(() => {
      result.current.setItems((prev) =>
        prev.map((item) => (item.id === 'a' ? { ...item, name: 'A2' } : item))
      );
    });

    const data = getAdminQueryClient().getQueryData<
      InfiniteData<PaginatedResponse<{ id: string; name: string }>>
    >(['pages-test', {}]);
    expect(data?.pages).toHaveLength(2);
    expect(data?.pageParams).toEqual([null, 'p2']);
    expect(data?.pages[0].items[0].name).toBe('A2');
    expect(data?.pages[1].items[0].id).toBe('b');
  });

  it('loads every page when fetchAll is set', async () => {
    const fetcher = vi.fn(async ({ cursor }: { cursor: string | null }) => {
      if (!cursor) {
        return { items: [{ id: 'a' }], nextCursor: 'p2' };
      }
      return { items: [{ id: 'b' }], nextCursor: null };
    });
    const { result } = renderHook(() =>
      usePaginatedList<{ id: string }, Record<string, never>>({
        queryKey: ['fetch-all-test'],
        defaultFilters: {},
        fetchAll: true,
        fetcher,
      })
    );

    await waitFor(() => expect(result.current.items.map((item) => item.id)).toEqual(['a', 'b']));
    expect(result.current.hasMore).toBe(false);
  });
});

describe('useExhaustPages', () => {
  it('requests the next page while a search is active', async () => {
    const loadMore = vi.fn(async () => undefined);
    const { rerender } = renderHook(
      ({ active, hasMore }: { active: boolean; hasMore: boolean }) =>
        useExhaustPages(active, {
          hasMore,
          isLoading: false,
          isLoadingMore: false,
          error: '',
          loadMore,
        }),
      { initialProps: { active: true, hasMore: true } }
    );

    await waitFor(() => expect(loadMore).toHaveBeenCalledTimes(1));
    rerender({ active: false, hasMore: true });
    expect(loadMore).toHaveBeenCalledTimes(1);
  });
});
