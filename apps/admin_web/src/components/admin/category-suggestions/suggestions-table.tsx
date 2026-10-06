'use client';

import { useEffect } from 'react';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import type { CategorySuggestion } from '../../../lib/api-client-category-suggestions';
import {
  AdminDataTableCell,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { Select } from '../../ui/select';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { StatusBadge } from '../../ui/status-badge';
import { SuggestionDetail } from './suggestion-detail';

interface SuggestionsTableProps {
  items: CategorySuggestion[];
  isLoading: boolean;
  isLoadingMore?: boolean;
  error?: string;
  summary?: string;
  source?: string;
  onSourceChange?: (source: string) => void;
  onReload: () => void;
  hasMore?: boolean;
  onLoadMore?: () => void;
}

export function SuggestionsTable({
  items,
  isLoading,
  isLoadingMore = false,
  error = '',
  summary,
  source = '',
  onSourceChange,
  onReload,
  hasMore = false,
  onLoadMore,
}: SuggestionsTableProps) {
  const expanded = useExpandedRecord({ paramName: 'suggestion' });
  const isBusy = items.some(
    (item) =>
      item.enrichment_status === 'queued' || item.enrichment_status === 'running'
  );
  const openInList = items.some((item) => item.id === expanded.expandedId);

  useEffect(() => {
    if (!isBusy) {
      return;
    }
    const timer = window.setInterval(() => {
      onReload();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [isBusy, onReload]);

  const detail = expanded.expandedId ? (
    <SuggestionDetail
      key={expanded.expandedId}
      suggestionId={expanded.expandedId}
      onClose={() => expanded.collapse()}
      onReload={onReload}
    />
  ) : null;

  return (
    <div className='space-y-4'>
      <ResourceTableShell
        ariaLabel='Category suggestions'
        rows={items}
        getLabel={(item) => `suggestion ${item.id}`}
        middleColumnCount={6}
        hasActions={false}
        isLoading={isLoading}
        isLoadingMore={isLoadingMore}
        hasMore={hasMore}
        onLoadMore={onLoadMore}
        error={error}
        emptyLabel='No category suggestions yet.'
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={openInList ? detail : null}
        filters={
          <AdminFilterBar summary={summary}>
            <AdminFilterField label='Source' htmlFor='suggestion-source-filter'>
              <Select
                id='suggestion-source-filter'
                value={source}
                onChange={(event) => onSourceChange?.(event.target.value)}
              >
                <option value=''>Any</option>
                <option value='import'>Import</option>
                <option value='scan'>Scan</option>
              </Select>
            </AdminFilterField>
          </AdminFilterBar>
        }
        head={
          <>
            <AdminDataTableHeadCell>Requested name</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Status
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Enrichment
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Activities
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Suggested name
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Source
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <span className='font-medium'>{item.requested_name}</span>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <StatusBadge status={item.status} />
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {item.enrichment_status}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {item.activity_count}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {item.suggested_name || '—'}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {item.source || '—'}
            </AdminDataTableCell>
          </>
        )}
      />
      {expanded.expandedId && !openInList && !isLoading ? detail : null}
    </div>
  );
}
