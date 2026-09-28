'use client';

import { useEffect, useRef } from 'react';

import { ADMIN_LIST_AUTO_PAGE_CAP } from '@/lib/admin-list-query';

interface ExhaustList {
  hasMore: boolean;
  isLoading: boolean;
  isLoadingMore: boolean;
  error?: string;
  loadMore: () => Promise<void>;
}

/**
 * While `active` (a non-empty table search), request further pages so a
 * client-side filter can see rows past the first page. Stops on error, when
 * the cursor is exhausted, or after `ADMIN_LIST_AUTO_PAGE_CAP` extra pages.
 */
export function useExhaustPages(active: boolean, list: ExhaustList) {
  const extraPages = useRef(0);
  const { hasMore, isLoading, isLoadingMore, error, loadMore } = list;

  useEffect(() => {
    if (!active) {
      extraPages.current = 0;
      return;
    }
    if (!hasMore || isLoading || isLoadingMore || error) {
      return;
    }
    if (extraPages.current >= ADMIN_LIST_AUTO_PAGE_CAP) {
      return;
    }
    extraPages.current += 1;
    void loadMore();
  }, [active, error, hasMore, isLoading, isLoadingMore, loadMore]);
}
