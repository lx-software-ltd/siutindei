'use client';

import { useQueryState } from 'nuqs';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import {
  listImportJobs,
  type ImportJobListItem,
} from '../../../lib/api-client-org-review';
import {
  AdminDataTableCell,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminFieldGrid } from '../../ui/admin-field-grid';
import { AdminReadOnlyValue } from '../../ui/admin-read-only-value';
import { Button } from '../../ui/button';
import { ResourceTableShell } from '../../ui/resource-table-shell';

function formatWhen(value?: string) {
  return value ? new Date(value).toLocaleString() : '—';
}

function organizationSummary(item: ImportJobListItem) {
  const counts = item.summary?.organizations;
  if (!counts) {
    return '—';
  }
  const captured = item.summary?.captured_categories;
  const base = `created ${counts.created}, updated ${counts.updated}`;
  if (!captured) {
    return base;
  }
  return `${base}; ${captured} categories captured`;
}

function modeLabel(item: ImportJobListItem) {
  return item.dry_run ? 'Dry run' : item.status;
}

function ImportJobSummary({ job }: { job: ImportJobListItem }) {
  const warnings = job.file_warnings ?? [];
  return (
    <AdminEditorPanel>
      <AdminFieldGrid columns={2}>
        <AdminReadOnlyValue label='When'>
          {formatWhen(job.created_at)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='File' mono>
          {job.object_key}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Mode'>{modeLabel(job)}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Organizations'>
          {organizationSummary(job)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Results'>
          {job.result_count ?? '—'}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Updated'>
          {formatWhen(job.updated_at)}
        </AdminReadOnlyValue>
      </AdminFieldGrid>
      {warnings.length > 0 ? (
        <div className='space-y-1 text-sm text-slate-600'>
          <p className='font-semibold text-slate-900'>File warnings</p>
          <ul className='list-disc space-y-1 pl-5'>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </AdminEditorPanel>
  );
}

export function ImportHistoryPanel() {
  const [, setTab] = useQueryState('tab');
  const [, setJob] = useQueryState('job');
  const expanded = useExpandedRecord({ paramName: 'import-job' });
  const list = usePaginatedList<ImportJobListItem, Record<string, never>>({
    queryKey: adminQueryKeys.importJobs(),
    defaultFilters: {},
    errorPrefix: 'Failed to load imports',
    fetcher: async ({ cursor }) => {
      const response = await listImportJobs(cursor ?? undefined);
      return {
        items: response.items,
        nextCursor: response.next_cursor ?? null,
      };
    },
  });
  const expandedJob =
    list.items.find((item) => item.id === expanded.expandedId) ?? null;

  return (
    <div className='space-y-3'>
      <h2 className='sr-only'>Import history</h2>
      <p className='text-sm text-slate-600'>
        Open the organizations written by a previous import.
      </p>
      <ResourceTableShell
        ariaLabel='Import history'
        rows={list.items}
        getLabel={(item) => `import ${item.id}`}
        middleColumnCount={4}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={() => {
          void list.loadMore();
        }}
        error={list.error}
        emptyLabel='No imports yet.'
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={expandedJob ? <ImportJobSummary job={expandedJob} /> : null}
        head={
          <>
            <AdminDataTableHeadCell>When</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              File
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Mode
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Organizations
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>{formatWhen(item.created_at)}</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {item.object_key}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {modeLabel(item)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {organizationSummary(item)}
            </AdminDataTableCell>
          </>
        )}
        renderActions={(item) =>
          item.dry_run ? null : (
            <Button
              type='button'
              size='sm'
              variant='secondary'
              onClick={() => {
                void setJob(item.id);
                void setTab('review');
              }}
            >
              View orgs
            </Button>
          )
        }
      />
    </div>
  );
}
