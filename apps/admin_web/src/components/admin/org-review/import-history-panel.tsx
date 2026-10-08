'use client';

import { useState } from 'react';
import { useQueryState } from 'nuqs';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { runAdminImport } from '../../../lib/api-client-imports';
import {
  listImportJobs,
  type ImportJobListItem,
} from '../../../lib/api-client-org-review';
import {
  AdminDataTableCell,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import { RetryIcon, ViewIcon } from '../../icons/action-icons';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminFieldGrid } from '../../ui/admin-field-grid';
import { AdminReadOnlyValue } from '../../ui/admin-read-only-value';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { AdminRowActions } from '../../ui/admin-row-actions';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { StatusBanner } from '../../status-banner';

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

function canRetry(item: ImportJobListItem) {
  return (
    !item.dry_run &&
    item.status === 'completed' &&
    (item.summary?.organizations?.failed ?? 0) > 0
  );
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
  const [, setSection] = useQueryState('section');
  const [retryJob, setRetryJob] = useState<ImportJobListItem | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');
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

  async function retryFailed() {
    if (!retryJob) {
      return;
    }
    setIsRetrying(true);
    setRetryError('');
    try {
      await runAdminImport({
        object_key: retryJob.object_key,
        retry_failed: true,
      });
      setRetryJob(null);
      void list.refetch();
    } catch (err) {
      setRetryError(err instanceof Error ? err.message : 'Retry failed.');
    } finally {
      setIsRetrying(false);
    }
  }

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>Import history</h2>
      {retryError ? (
        <StatusBanner variant='error' kind='error'>
          {retryError}
        </StatusBanner>
      ) : null}
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
            <AdminRowActions
              actions={[
                {
                  key: 'retry',
                  label: 'Retry failed',
                  icon: <RetryIcon className='h-4 w-4' />,
                  hidden: !canRetry(item),
                  onClick: () => setRetryJob(item),
                },
                {
                  key: 'view',
                  label: 'View orgs',
                  icon: <ViewIcon className='h-4 w-4' />,
                  onClick: () => {
                    void setJob(item.id);
                    void setTab(null);
                    void setSection('catalog');
                  },
                },
              ]}
            />
          )
        }
      />
      <ConfirmDialog
        open={retryJob !== null}
        title='Retry failed organizations'
        message='Run the import again for organizations that failed. Organizations that already imported stay as they are.'
        confirmLabel='Retry failed'
        confirmLoading={isRetrying}
        confirmLoadingLabel='Retrying…'
        onConfirm={() => void retryFailed()}
        onCancel={() => setRetryJob(null)}
      />
    </div>
  );
}
