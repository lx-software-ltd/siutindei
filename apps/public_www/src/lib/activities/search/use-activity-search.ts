'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import type { Locale } from '@/content/locales';
import { fetchActivitySearch } from '@/lib/activities/search-client';
import {
  filtersToApiParams,
  type SearchFiltersState,
} from '@/lib/activities/search-params';
import type { ActivityListing } from '@/lib/activities/types';

export interface UseActivitySearchOptions {
  readonly filters: SearchFiltersState;
  readonly locale: Locale;
  readonly pageSize: number;
  readonly enabled?: boolean;
  readonly view?: 'card' | 'full';
}

export interface UseActivitySearchResult {
  readonly items: readonly ActivityListing[];
  readonly isLoading: boolean;
  readonly isLoadingMore: boolean;
  readonly errorMessage: string | null;
  readonly loadMoreError: string | null;
  readonly hasMore: boolean;
  readonly categoryMatch: 'exact' | 'legacy_fallback';
  readonly loadMore: () => void;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

export function useActivitySearch({
  filters,
  locale,
  pageSize,
  enabled = true,
  view = 'card',
}: UseActivitySearchOptions): UseActivitySearchResult {
  const [items, setItems] = useState<readonly ActivityListing[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(enabled);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const [categoryMatch, setCategoryMatch] = useState<
    'exact' | 'legacy_fallback'
  >('exact');
  const filtersKey = JSON.stringify(filters);
  const generation = useRef(0);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    const requestGeneration = generation.current + 1;
    generation.current = requestGeneration;
    setIsLoading(true);
    setIsLoadingMore(false);
    setErrorMessage(null);
    setLoadMoreError(null);
    setNextCursor(null);
    const apiParams = filtersToApiParams(filters);
    fetchActivitySearch(
      {
        ...apiParams,
        limit: pageSize,
        view,
      },
      { signal: controller.signal },
    )
      .then((response) => {
        if (requestGeneration !== generation.current) {
          return;
        }
        setItems(response.items);
        setNextCursor(response.nextCursor);
        setCategoryMatch(response.categoryMatch ?? 'exact');
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || requestGeneration !== generation.current) {
          return;
        }
        setItems([]);
        setNextCursor(null);
        setCategoryMatch('exact');
        setErrorMessage('error');
      })
      .finally(() => {
        if (!controller.signal.aborted && requestGeneration === generation.current) {
          setIsLoading(false);
        }
      });
    return () => {
      controller.abort();
    };
    // filtersKey is the stable identity for filters. locale is part of the
    // request only through copy, not the API, but a locale change should refetch
    // when q matching is locale-sensitive on the server.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, filtersKey, locale, pageSize, view]);

  const loadMore = useCallback(() => {
    if (!enabled || isLoading || isLoadingMore || !nextCursor) {
      return;
    }
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    const requestGeneration = generation.current;
    setIsLoadingMore(true);
    setLoadMoreError(null);
    const apiParams = filtersToApiParams(filters);
    fetchActivitySearch(
      {
        ...apiParams,
        cursor: nextCursor,
        limit: pageSize,
        view,
      },
      { signal: controller.signal },
    )
      .then((response) => {
        if (requestGeneration !== generation.current) {
          return;
        }
        setItems((current) => [...current, ...response.items]);
        setNextCursor(response.nextCursor);
        setCategoryMatch(response.categoryMatch ?? 'exact');
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || requestGeneration !== generation.current) {
          return;
        }
        setLoadMoreError('error');
      })
      .finally(() => {
        if (!controller.signal.aborted && requestGeneration === generation.current) {
          setIsLoadingMore(false);
        }
      });
  }, [enabled, filters, isLoading, isLoadingMore, nextCursor, pageSize, view]);

  return {
    items,
    isLoading: enabled ? isLoading : false,
    isLoadingMore,
    errorMessage,
    loadMoreError,
    hasMore: nextCursor !== null,
    categoryMatch,
    loadMore,
  };
}
