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
import { AdminKpiCard } from '../../ui/admin-kpi-card';
import { CategorySuggestionSettingsCard } from './settings-card';
import { SuggestionsTable } from './suggestions-table';

export function CategorySuggestionsPanel() {
  const list = usePaginatedList<CategorySuggestion, { source: string }>({
    queryKey: adminQueryKeys.categorySuggestions(),
    defaultFilters: { source: '' },
    errorPrefix: 'Could not load suggestions',
    fetcher: async ({ cursor, limit, source }) => {
      const page = await listCategorySuggestions({
        cursor: cursor ?? undefined,
        limit,
        source: source || undefined,
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
  const pendingActivities = summary?.pending_activity_total ?? 0;
  const stranded = summary?.stranded_activity_total ?? 0;
  const spending = `$${(summary?.month_cost_usd ?? 0).toFixed(4)}`;

  return (
    <div className='space-y-4'>
      {summaryError ? (
        <StatusBanner kind='error'>
          {summaryError}
        </StatusBanner>
      ) : null}
      <div className='grid gap-3 sm:grid-cols-3'>
        <AdminKpiCard label='Pending' value={pendingCount} />
        <AdminKpiCard
          label='Activities need category'
          value={pendingActivities}
        />
        <AdminKpiCard label='Spending per month' value={spending} />
      </div>
      {stranded > 0 ? (
        <p className='text-sm text-ink-700'>
          {stranded} remain after a decision that did not map them.
        </p>
      ) : null}
      <SuggestionsTable
        items={list.items}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        error={list.error}
        source={list.filters.source}
        onSourceChange={(source) => list.setFilter('source', source)}
        onReload={reload}
        hasMore={list.hasMore}
        onLoadMore={() => {
          void list.loadMore();
        }}
      />
      <CategorySuggestionSettingsCard />
    </div>
  );
}
