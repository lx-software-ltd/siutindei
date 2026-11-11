'use client';

import { useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import type { Locale } from '@/content/locales';
import { useSearchContext } from '@/components/shared/search/search-context';
import { buildSearchPageHref } from '@/lib/activities/map-search-url';
import { parseSearchViewMode, type SearchFiltersState } from '@/lib/activities/search-params';

/** Applies filters on the search page and keeps the current list or map view. */
export function useApplySearchFilters(locale: Locale): (next: SearchFiltersState) => void {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setFilters } = useSearchContext();

  return useCallback(
    (next: SearchFiltersState) => {
      setFilters(next);
      router.replace(
        buildSearchPageHref(locale, next, { view: parseSearchViewMode(searchParams) }),
      );
    },
    [locale, router, searchParams, setFilters],
  );
}
