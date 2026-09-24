'use client';

import { useCallback, useEffect, useState } from 'react';
import { useQueryState } from 'nuqs';

import {
  getCategorySuggestionSummary,
  listCategorySuggestions,
  type CategorySuggestion,
  type CategorySuggestionSummary,
} from '../../../lib/api-client-category-suggestions';
import { Card } from '../../ui/card';
import { Select } from '../../ui/select';
import { StatusBanner } from '../../status-banner';
import { CategorySuggestionSettingsCard } from './settings-card';
import { SuggestionDetail } from './suggestion-detail';
import { SuggestionsTable } from './suggestions-table';

export function CategorySuggestionsPanel() {
  const [suggestionId, setSuggestionId] = useQueryState('suggestion');
  const [status, setStatus] = useState('');
  const [items, setItems] = useState<CategorySuggestion[]>([]);
  const [summary, setSummary] = useState<CategorySuggestionSummary | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [page, counts] = await Promise.all([
        listCategorySuggestions({ status: status || undefined }),
        getCategorySuggestionSummary(),
      ]);
      setItems(page.items);
      setNextCursor(page.next_cursor || null);
      setSummary(counts);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load suggestions.');
    }
  }, [status]);

  useEffect(() => {
    let cancelled = false;
    listCategorySuggestions({ status: status || undefined })
      .then((page) => {
        if (cancelled) {
          return null;
        }
        setItems(page.items);
        setNextCursor(page.next_cursor || null);
        return getCategorySuggestionSummary();
      })
      .then((counts) => {
        if (!cancelled && counts) {
          setSummary(counts);
          setError('');
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : 'Could not load suggestions.'
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [status]);

  const pendingCount = summary?.by_status.pending ?? 0;

  return (
    <div className='space-y-6'>
      <CategorySuggestionSettingsCard />
      {error ? (
        <StatusBanner variant='error' title='Error'>
          {error}
        </StatusBanner>
      ) : null}
      <Card
        title='Category suggestions'
        description={`${pendingCount} pending. ${summary?.pending_activity_total ?? 0} activities still need a category. This month $${(summary?.month_cost_usd ?? 0).toFixed(4)}.`}
      >
        <div className='mb-4 max-w-xs'>
          <Select
            aria-label='Status'
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value=''>Any status</option>
            <option value='pending'>Pending</option>
            <option value='approved'>Approved</option>
            <option value='merged'>Merged</option>
            <option value='rejected'>Rejected</option>
          </Select>
        </div>
        <SuggestionsTable
          items={items}
          onOpen={(item) => void setSuggestionId(item.id)}
          onReload={() => void load()}
          nextCursor={nextCursor}
          onLoadMore={() => {
            if (!nextCursor) {
              return;
            }
            void listCategorySuggestions({
              status: status || undefined,
              cursor: nextCursor,
            }).then((page) => {
              setItems((current) => [...current, ...page.items]);
              setNextCursor(page.next_cursor || null);
            });
          }}
        />
      </Card>
      {suggestionId ? (
        <SuggestionDetail
          key={suggestionId}
          suggestionId={suggestionId}
          onClose={() => void setSuggestionId(null)}
        />
      ) : null}
    </div>
  );
}
