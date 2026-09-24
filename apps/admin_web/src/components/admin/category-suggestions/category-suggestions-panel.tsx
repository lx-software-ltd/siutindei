'use client';

import { useCallback, useEffect, useState } from 'react';

import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import {
  getCategorySuggestionSummary,
  listCategorySuggestions,
  type CategorySuggestion,
  type CategorySuggestionSummary,
} from '../../../lib/api-client-category-suggestions';
import { StatusBanner } from '../../status-banner';
import { CategorySuggestionSettingsCard } from './settings-card';
import { SuggestionsTable } from './suggestions-table';

interface SuggestionFilters {
  status: string;
}

const DEFAULT_SUGGESTION_FILTERS: SuggestionFilters = {
  status: '',
};

export function CategorySuggestionsPanel() {
  const list = usePaginatedList<CategorySuggestion, SuggestionFilters>({
    queryKey: adminQueryKeys.categorySuggestions(DEFAULT_SUGGESTION_FILTERS),
    defaultFilters: DEFAULT_SUGGESTION_FILTERS,
    errorPrefix: 'Could not load suggestions',
    fetcher: async ({ cursor, limit, status }) => {
      const page = await listCategorySuggestions({
        status: status || undefined,
        cursor: cursor ?? undefined,
        limit,
      });
      return {
        items: page.items,
        nextCursor: page.next_cursor || null,
      };
    },
  });
  const [summary, setSummary] = useState<CategorySuggestionSummary | null>(null);
  const [summaryError, setSummaryError] = useState('');

  const { refetch } = list;
  const reload = useCallback(() => {
    void refetch();
    void getCategorySuggestionSummary()
      .then((counts) => {
        setSummary(counts);
      })
      .catch(() => {
        // The table already surfaces list errors.
      });
  }, [refetch]);

  useEffect(() => {
    let cancelled = false;
    getCategorySuggestionSummary()
      .then((counts) => {
        if (!cancelled) {
          setSummary(counts);
          setSummaryError('');
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setSummaryError(
            err instanceof Error ? err.message : 'Could not load suggestions.'
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const pendingCount = summary?.by_status.pending ?? 0;
  const stranded = summary?.stranded_activity_total ?? 0;
  const strandedNote =
    stranded > 0
      ? ` ${stranded} remain after a decision that did not map them.`
      : '';
  const summaryText =
    `${pendingCount} pending. ${summary?.pending_activity_total ?? 0} ` +
    `activities still need a category.${strandedNote} This month ` +
    `$${(summary?.month_cost_usd ?? 0).toFixed(4)}.`;

  return (
    <div className='space-y-6'>
      <CategorySuggestionSettingsCard />
      {summaryError ? (
        <StatusBanner variant='error' title='Error'>
          {summaryError}
        </StatusBanner>
      ) : null}
      <SuggestionsTable
        items={list.items}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        error={list.error}
        summary={summaryText}
        status={list.filters.status}
        onStatusChange={(status) => list.setFilter('status', status)}
        onReload={reload}
        hasMore={list.hasMore}
        onLoadMore={() => {
          void list.loadMore();
        }}
      />
    </div>
  );
}
