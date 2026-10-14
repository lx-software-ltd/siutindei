'use client';

import { useState } from 'react';
import { useQueryState } from 'nuqs';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import {
  useCapturedCategoryNames,
  useImportJob,
} from '../../../hooks/use-import-job';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminTabLabel, formatAdminPageName } from '../../../lib/admin-page-name';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { formatDateTime } from '../../../lib/date-utils';
import { runAdminImport } from '../../../lib/api-client-imports';
import { retryDataQualityRun } from '../../../lib/api-client-data-quality';
import {
  formatCapturedCategories,
  formatImportJobMode,
  formatImportJobSource,
  formatImportResultHeader,
  formatImportResultNotes,
  groupImportResults,
  importResultWorkspaceHref,
  previewImportRows,
  type ImportResultGroup,
} from '../../../lib/import-job-results';
import type { AdminImportResult } from '../../../lib/api-client-imports';
import {
  listImportJobs,
  type ImportJobListItem,
} from '../../../lib/api-client-org-review';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import { ADMIN_TABLE_EMPTY, AdminTableTime } from '../../ui/admin-table-value';
import { RetryIcon, ViewIcon } from '../../icons/action-icons';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminFieldGrid } from '../../ui/admin-field-grid';
import { AdminReadOnlyValue } from '../../ui/admin-read-only-value';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { AdminRowActions } from '../../ui/admin-row-actions';
import { Button } from '../../ui/button';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { StatusBanner } from '../../status-banner';
import { StatusBadge, type StatusBadgeTone } from '../../ui/status-badge';

const HISTORY_LINK_REFRESH_MS = 30 * 60 * 1000;
const PAGE_NAME = formatAdminPageName('Imports', adminTabLabel.history);

const RESULT_STATUS_TONE: Record<string, StatusBadgeTone> = {
  created: 'green',
  updated: 'blue',
  unchanged: 'slate',
  failed: 'red',
  skipped: 'yellow',
};

function formatWhen(value?: string) {
  return formatDateTime(value);
}

function ImportFileLink({ job }: { job: ImportJobListItem }) {
  if (!job.download_url) {
    return <>{job.object_key}</>;
  }
  return (
    <a
      href={job.download_url}
      target='_blank'
      rel='noreferrer'
      className='underline underline-offset-2 hover:text-slate-900'
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      {job.object_key}
    </a>
  );
}

function canRetry(item: ImportJobListItem) {
  return (
    !item.dry_run &&
    item.status === 'completed' &&
    (item.summary?.organizations?.failed ?? 0) > 0
  );
}

function ImportResultKey({
  row,
  results,
  dryRun,
}: {
  row: AdminImportResult;
  results: readonly AdminImportResult[];
  dryRun: boolean;
}) {
  const href = importResultWorkspaceHref(row, results, { dryRun });
  if (!href) {
    return <span className='text-slate-800'>{row.key}</span>;
  }
  return (
    <a
      href={href}
      className='underline underline-offset-2 hover:text-slate-900'
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      {row.key}
    </a>
  );
}

function ImportResultGroupList({
  group,
  results,
  dryRun,
}: {
  group: ImportResultGroup;
  results: readonly AdminImportResult[];
  dryRun: boolean;
}) {
  const [showAll, setShowAll] = useState(false);
  const preview = previewImportRows(group.rows, showAll);
  return (
    <div className='space-y-1 text-sm text-slate-600'>
      <p className='font-semibold text-slate-900'>
        {group.label}
        {group.counts ? ` · ${group.counts}` : ''}
      </p>
      <ul className='list-disc space-y-1 pl-5'>
        {preview.rows.map((row, index) => {
          const notes = formatImportResultNotes(row);
          return (
            <li key={`${row.type}-${row.key}-${index}`}>
              <span className='me-2'>
                <StatusBadge
                  status={row.status}
                  tone={RESULT_STATUS_TONE[row.status]}
                />
              </span>
              <ImportResultKey row={row} results={results} dryRun={dryRun} />
              {notes ? <span> — {notes}</span> : null}
            </li>
          );
        })}
      </ul>
      {preview.hidden > 0 ? (
        <Button
          type='button'
          variant='ghost'
          size='sm'
          onClick={(event) => {
            event.stopPropagation();
            setShowAll(true);
          }}
        >
          Show all {group.rows.length}
        </Button>
      ) : null}
    </div>
  );
}

function ImportJobResults({
  job,
  detail,
}: {
  job: ImportJobListItem;
  detail: ReturnType<typeof useImportJob>;
}) {
  const results = detail.data?.results ?? [];
  const groups = groupImportResults(results);
  const header = formatImportResultHeader(
    results.length,
    detail.data?.summary.warnings ?? job.summary.warnings ?? 0,
    detail.data?.summary.errors ?? job.summary.errors ?? 0
  );
  if (detail.isPending) {
    return <p className='text-sm text-slate-500'>Loading…</p>;
  }
  if (detail.isError) {
    const fallback =
      job.result_count == null
        ? ADMIN_TABLE_EMPTY
        : formatImportResultHeader(job.result_count);
    const message =
      detail.error instanceof Error
        ? detail.error.message
        : 'Failed to load results';
    return (
      <div className='space-y-1 text-sm text-slate-600'>
        <p>{fallback}</p>
        <p>{message}</p>
      </div>
    );
  }
  if (results.length === 0) {
    return (
      <div className='space-y-1 text-sm text-slate-600'>
        {job.dry_run ? <p>Predicted outcomes; nothing was written.</p> : null}
        <p>No per-row results.</p>
      </div>
    );
  }
  return (
    <div className='space-y-3 text-sm text-slate-600'>
      {job.dry_run ? <p>Predicted outcomes; nothing was written.</p> : null}
      <p>{header}</p>
      {groups.map((group) => (
        <ImportResultGroupList
          key={group.type}
          group={group}
          results={results}
          dryRun={job.dry_run}
        />
      ))}
    </div>
  );
}

function ImportJobCategories({
  job,
  detail,
}: {
  job: ImportJobListItem;
  detail: ReturnType<typeof useImportJob>;
}) {
  const count =
    detail.data?.summary.captured_categories ??
    job.summary.captured_categories ??
    0;
  const ids =
    detail.data?.summary.captured_category_ids ??
    job.summary.captured_category_ids ??
    [];
  const names = useCapturedCategoryNames(job.id, ids);
  const unavailable = names.isError
    ? ids.length
    : (names.data?.unavailable ?? 0);
  return (
    <>{formatCapturedCategories(count, names.data?.names ?? [], unavailable)}</>
  );
}

function ImportRunLink({ runId }: { runId: string }) {
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  return (
    <div className='space-y-2'>
      <a
        className='underline underline-offset-2'
        href={`/admin/dashboard?section=data-quality&tab=runs&run=${encodeURIComponent(runId)}`}
      >
        {runId}
      </a>
      <div>
        <Button
          type='button'
          variant='secondary'
          size='sm'
          loading={pending}
          onClick={() => {
            setPending(true);
            setError('');
            void retryDataQualityRun(runId)
              .catch((err: unknown) => {
                setError(err instanceof Error ? err.message : 'Retry failed.');
              })
              .finally(() => setPending(false));
          }}
        >
          Run again
        </Button>
      </div>
      {error ? <p className='text-sm text-red-700'>{error}</p> : null}
    </div>
  );
}

function ImportJobSummary({ job }: { job: ImportJobListItem }) {
  const detail = useImportJob(job.id, job.status);
  return (
    <AdminEditorPanel>
      <AdminFieldGrid columns={2}>
        <AdminReadOnlyValue label='Timestamp'>
          {formatWhen(job.created_at)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Last changed'>
          {formatWhen(job.updated_at)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Source'>
          {formatImportJobSource(job.source)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Mode'>
          {formatImportJobMode(job)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='File' mono>
          <ImportFileLink job={job} />
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Captured categories'>
          <ImportJobCategories job={job} detail={detail} />
        </AdminReadOnlyValue>
        {job.summary.data_quality_run_id ? (
          <AdminReadOnlyValue label='Data quality' span='full'>
            <ImportRunLink runId={job.summary.data_quality_run_id} />
          </AdminReadOnlyValue>
        ) : null}
        <AdminReadOnlyValue label='Results' span='full'>
          <ImportJobResults job={job} detail={detail} />
        </AdminReadOnlyValue>
      </AdminFieldGrid>
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
    refetchInterval: HISTORY_LINK_REFRESH_MS,
    refetchOnWindowFocus: true,
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
        allow_updates: retryJob.allow_updates !== false,
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
      <h2 className='sr-only'>{PAGE_NAME}</h2>
      {retryError ? (
        <StatusBanner kind='error'>
          {retryError}
        </StatusBanner>
      ) : null}
      <ResourceTableShell
        ariaLabel={PAGE_NAME}
        rows={list.items}
        getLabel={(item) => `import ${item.id}`}
        middleColumnCount={3}
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
            <AdminDataTableHeadCell>Timestamp</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Source
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Mode
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <AdminTableTime value={item.created_at} emphasis />
              <AdminDataTableCellMeta until='secondary' label='Source'>
                {formatImportJobSource(item.source)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary'>
                {formatImportJobMode(item)}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {formatImportJobSource(item.source)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {formatImportJobMode(item)}
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
