'use client';

import { useEffect } from 'react';

import type { CategorySuggestion } from '../../../lib/api-client-category-suggestions';
import { DataTable } from '../../ui/data-table';
import { StatusBadge } from '../../ui/status-badge';

interface SuggestionsTableProps {
  items: CategorySuggestion[];
  onOpen: (item: CategorySuggestion) => void;
  onReload: () => void;
  nextCursor?: string | null;
  onLoadMore?: () => void;
}

export function SuggestionsTable({
  items,
  onOpen,
  onReload,
  nextCursor,
  onLoadMore,
}: SuggestionsTableProps) {
  const isBusy = items.some(
    (item) =>
      item.enrichment_status === 'queued' || item.enrichment_status === 'running'
  );

  useEffect(() => {
    if (!isBusy) {
      return;
    }
    const timer = window.setInterval(() => {
      onReload();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [isBusy, onReload]);

  return (
    <DataTable
      columns={[
        {
          key: 'name',
          header: 'Requested name',
          primary: true,
          render: (item: CategorySuggestion) => item.requested_name,
        },
        {
          key: 'status',
          header: 'Status',
          render: (item: CategorySuggestion) => (
            <StatusBadge status={item.status} />
          ),
        },
        {
          key: 'enrichment',
          header: 'Enrichment',
          render: (item: CategorySuggestion) => item.enrichment_status,
        },
        {
          key: 'count',
          header: 'Activities',
          render: (item: CategorySuggestion) => item.activity_count,
        },
        {
          key: 'suggestion',
          header: 'Suggested name',
          render: (item: CategorySuggestion) => item.suggested_name || '—',
        },
      ]}
      data={items}
      keyExtractor={(item) => item.id}
      onEdit={(item) => onOpen(item)}
      nextCursor={nextCursor}
      onLoadMore={onLoadMore}
      emptyMessage='No category suggestions yet.'
    />
  );
}
