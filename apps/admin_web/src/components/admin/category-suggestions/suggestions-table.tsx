'use client';

import { useEffect } from 'react';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { adminTabLabel, formatAdminPageName } from '../../../lib/admin-page-name';
import type { CategorySuggestion } from '../../../lib/api-client-category-suggestions';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import {
  adminTableText,
  AdminTableName,
  AdminTableNumber,
} from '../../ui/admin-table-value';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { Select } from '../../ui/select';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { StatusBadge } from '../../ui/status-badge';
import { SuggestionDetail } from './suggestion-detail';

const PAGE_NAME = formatAdminPageName('Categories', adminTabLabel.suggestions);

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
      onReload={onReload}
    />
  ) : null;

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>{PAGE_NAME}</h2>
      {summary ? <p className='text-sm text-slate-700'>{summary}</p> : null}
      <ResourceTableShell
        ariaLabel={PAGE_NAME}
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
          <AdminFilterBar>
            <AdminFilterField>
              <Select
                id='suggestion-source-filter'
                aria-label='Source'
                value={source}
                onChange={(event) => onSourceChange?.(event.target.value)}
              >
                <option value=''>Any source</option>
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
              <AdminTableName>{item.requested_name}</AdminTableName>
              <AdminDataTableCellMeta until='secondary'>
                <StatusBadge status={item.status} />
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary'>
                <StatusBadge status={item.enrichment_status} />
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='tertiary'>
                <AdminTableNumber>{item.activity_count}</AdminTableNumber>
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='tertiary' label='Suggested'>
                {adminTableText(item.suggested_name)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='tertiary' label='Source'>
                {adminTableText(item.source)}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <StatusBadge status={item.status} />
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <StatusBadge status={item.enrichment_status} />
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <AdminTableNumber>{item.activity_count}</AdminTableNumber>
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {adminTableText(item.suggested_name)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {adminTableText(item.source)}
            </AdminDataTableCell>
          </>
        )}
      />
      {expanded.expandedId && !openInList && !isLoading ? detail : null}
    </div>
  );
}
