'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQueryState } from 'nuqs';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { ApiError } from '../../../lib/api-client';
import {
  bulkOrgReview,
  getOrgReviewDetail,
  getOrgReviewSummary,
  listOrgReviews,
  type OrgReviewDetail,
  type OrgReviewIssue,
  type OrgReviewListItem,
  type OrgReviewSummary,
} from '../../../lib/api-client-org-review';
import { StatusBanner } from '../../status-banner';
import {
  AdminDataTableCell,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { Button } from '../../ui/button';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Input } from '../../ui/input';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { Select } from '../../ui/select';
import { StatusBadge } from '../../ui/status-badge';
import { BULK_FIELDS_FORM_ID, BulkFieldsDialog } from './bulk-fields-dialog';

const ISSUE_OPTIONS = [
  ['', 'Any issue'],
  ['missing_description', 'Missing description'],
  ['no_locations', 'No locations'],
  ['no_activities', 'No activities'],
  ['missing_coordinates', 'Missing map pin'],
  ['missing_pricing', 'Missing price'],
  ['missing_schedule', 'Missing schedule'],
  ['pending_category', 'Pending category'],
  ['no_contact', 'No contact'],
  ['no_media', 'No photos'],
  ['source_attribution', 'Template or source line'],
];

type BulkAction = 'approve' | 'reject' | 'reopen' | 'set_fields';

interface ReviewQueueFilters {
  review_status: string;
  source: string;
  issue: string;
  has_blockers: string;
  q: string;
  import_job_id: string;
  sort: 'name' | 'last_imported_at';
}

const DEFAULT_REVIEW_FILTERS: ReviewQueueFilters = {
  review_status: 'pending_review',
  source: '',
  issue: '',
  has_blockers: '',
  q: '',
  import_job_id: '',
  sort: 'name',
};

function sectionForIssue(entityType: string) {
  if (entityType === 'location') {
    return 'locations';
  }
  if (entityType === 'activity') {
    return 'activities';
  }
  return 'organizations';
}

function issueSummary(item: OrgReviewListItem) {
  if (item.issues.length === 0) {
    return 'Ready';
  }
  return item.issues
    .slice(0, 3)
    .map((entry) => entry.message)
    .join('; ');
}

function ReviewDetail({
  detail,
  onOpenIssue,
  onOpenOrganization,
}: {
  detail: OrgReviewDetail | null;
  onOpenIssue: (entry: OrgReviewIssue) => void;
  onOpenOrganization: () => void;
}) {
  if (!detail) {
    return <p className='text-sm text-slate-600'>Loading details...</p>;
  }

  return (
    <AdminEditorPanel>
      <p className='text-sm text-slate-600'>
        Fix a row by opening the record, then come back and approve.
      </p>
      <button
        type='button'
        className='text-sm text-slate-900 underline'
        onClick={onOpenOrganization}
      >
        Edit organization
      </button>
      <ul className='space-y-2 text-sm text-slate-700'>
        {detail.issues.length === 0 && <li>Nothing is missing.</li>}
        {detail.issues.map((entry) => (
          <li key={`${entry.entity_id}-${entry.code}`}>
            <span className='font-medium'>{entry.message}</span>
            <button
              type='button'
              className='ml-2 text-slate-900 underline'
              onClick={() => onOpenIssue(entry)}
            >
              Fix
            </button>
          </li>
        ))}
      </ul>
    </AdminEditorPanel>
  );
}

export function ReviewQueuePanel() {
  const [jobParam, setJobParam] = useQueryState('job');
  const [, setSection] = useQueryState('section');
  const [, setEdit] = useQueryState('edit');
  const [, setOrganization] = useQueryState('organization');
  const [, setLocation] = useQueryState('location');
  const [, setActivity] = useQueryState('activity');
  const expanded = useExpandedRecord({ paramName: 'review' });
  const defaultFilters = useMemo(
    () => ({
      ...DEFAULT_REVIEW_FILTERS,
      import_job_id: jobParam ?? '',
    }),
    // The hook reads defaults once. Later job changes go through setFilter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );
  const list = usePaginatedList<OrgReviewListItem, ReviewQueueFilters>({
    queryKey: adminQueryKeys.orgReview(),
    defaultFilters,
    limit: 50,
    debounceKeys: ['q', 'source'],
    errorPrefix: 'Failed to load the review queue',
    fetcher: async ({
      cursor,
      limit,
      review_status,
      source,
      issue,
      has_blockers,
      q,
      import_job_id,
      sort,
    }) => {
      const page = await listOrgReviews({
        review_status: review_status || undefined,
        source: source || undefined,
        issue: issue || undefined,
        has_blockers:
          has_blockers === '' ? undefined : has_blockers === 'true',
        q: q || undefined,
        import_job_id: import_job_id || undefined,
        sort: sort === 'last_imported_at' ? sort : undefined,
        cursor: cursor ?? undefined,
        limit,
      });
      return {
        items: page.items,
        nextCursor: page.next_cursor ?? null,
      };
    },
  });
  const [summary, setSummary] = useState<OrgReviewSummary | null>(null);
  const [detail, setDetail] = useState<OrgReviewDetail | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [force, setForce] = useState(false);
  const [showFields, setShowFields] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [activeBulk, setActiveBulk] = useState<BulkAction | null>(null);
  const { items, filters, setFilter, refetch, loadMore, hasMore, isLoading, isLoadingMore } =
    list;

  const refreshSummary = useCallback(async () => {
    try {
      setSummary(await getOrgReviewSummary());
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Failed to load the review queue.'
      );
    }
  }, []);

  useEffect(() => {
    void refreshSummary();
  }, [refreshSummary]);

  useEffect(() => {
    const nextJob = jobParam ?? '';
    if (filters.import_job_id !== nextJob) {
      setFilter('import_job_id', nextJob);
    }
  }, [filters.import_job_id, jobParam, setFilter]);

  useEffect(() => {
    setSelected(new Set());
  }, [
    filters.review_status,
    filters.source,
    filters.issue,
    filters.has_blockers,
    filters.q,
    filters.import_job_id,
    filters.sort,
  ]);

  useEffect(() => {
    const id = expanded.expandedId;
    if (!id) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setDetail(null);
    getOrgReviewDetail(id)
      .then((row) => {
        if (!cancelled) {
          setDetail(row);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : 'Failed to load details.'
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [expanded.expandedId]);

  async function runBulk(
    action: BulkAction,
    fields?: Record<string, string>
  ) {
    const orgIds = Array.from(selected);
    if (orgIds.length === 0) {
      setError('Select at least one organization.');
      return;
    }
    setActiveBulk(action);
    setError('');
    setNotice('');
    try {
      const response = await bulkOrgReview({
        org_ids: orgIds,
        action,
        force: action === 'approve' ? force : undefined,
        fields,
      });
      const blocked = response.results.filter((item) => item.status === 'blocked');
      const failed = response.results.filter((item) => item.status === 'error');
      const ok = response.results.filter((item) => item.status === 'ok');
      setNotice(
        `Updated ${ok.length}. ${blocked.length} still missing details. ${failed.length} failed.`
      );
      setShowFields(false);
      setSelected(new Set());
      await Promise.all([refetch(), refreshSummary()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bulk update failed.');
    } finally {
      setActiveBulk(null);
    }
  }

  function openOrganization(orgId: string) {
    void setSection('organizations');
    void setOrganization(orgId);
    void setLocation(null);
    void setActivity(null);
    void setEdit(null);
  }

  function openIssue(entry: OrgReviewIssue) {
    if (entry.entity_type === 'organization') {
      openOrganization(entry.entity_id);
      return;
    }
    void setOrganization(null);
    void setEdit(null);
    void setSection(sectionForIssue(entry.entity_type));
    if (entry.entity_type === 'location') {
      void setLocation(entry.entity_id);
      void setActivity(null);
      return;
    }
    if (entry.entity_type === 'activity') {
      void setActivity(entry.entity_id);
      void setLocation(null);
      return;
    }
    void setLocation(null);
    void setActivity(null);
    void setEdit(entry.entity_id);
  }

  const pendingCount = summary?.by_review_status.pending_review ?? 0;
  const isSaving = activeBulk !== null;
  const allSelected =
    items.length > 0 && items.every((item) => selected.has(item.id));
  const openDetail =
    detail && detail.id === expanded.expandedId ? detail : null;

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>Review queue</h2>
      <p className='text-sm text-slate-600'>
        Imported organizations stay pending until you release them. Public
        search keeps the current listings until ORG_REVIEW_GATE_ENABLED is
        turned on. After a release, search can stay cached for up to 5 minutes.
      </p>
      <div className='grid gap-3 sm:grid-cols-3'>
        <div className='rounded-lg border border-slate-200 p-3'>
          <p className='text-xs text-slate-500'>Pending review</p>
          <p className='text-2xl font-semibold text-slate-900'>{pendingCount}</p>
        </div>
        <div className='rounded-lg border border-slate-200 p-3'>
          <p className='text-xs text-slate-500'>With missing details</p>
          <p className='text-2xl font-semibold text-slate-900'>
            {summary?.with_blockers ?? 0}
          </p>
        </div>
        <div className='rounded-lg border border-slate-200 p-3'>
          <p className='text-xs text-slate-500'>Approved</p>
          <p className='text-2xl font-semibold text-slate-900'>
            {summary?.by_review_status.approved ?? 0}
          </p>
        </div>
      </div>
      <ResourceTableShell
        ariaLabel='Review queue'
        rows={items}
        getLabel={(item) => `organization ${item.id}`}
        middleColumnCount={5}
        hasActions={false}
        isLoading={isLoading}
        isLoadingMore={isLoadingMore}
        hasMore={hasMore}
        onLoadMore={() => {
          void loadMore();
        }}
        error={list.error}
        emptyLabel='No organizations match these filters.'
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={
          <ReviewDetail
            detail={openDetail}
            onOpenIssue={openIssue}
            onOpenOrganization={() => {
              if (openDetail) {
                openOrganization(openDetail.id);
              }
            }}
          />
        }
        filters={
          <AdminFilterBar
            trailing={
              jobParam ? (
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => {
                    void setJobParam(null);
                  }}
                >
                  Clear import filter
                </Button>
              ) : null
            }
          >
            <AdminFilterField label='Review' htmlFor='review-status-filter'>
              <Select
                id='review-status-filter'
                value={filters.review_status}
                onChange={(event) =>
                  setFilter('review_status', event.target.value)
                }
              >
                <option value=''>All</option>
                <option value='pending_review'>Pending review</option>
                <option value='approved'>Approved</option>
                <option value='rejected'>Rejected</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Missing detail' htmlFor='review-issue-filter'>
              <Select
                id='review-issue-filter'
                value={filters.issue}
                onChange={(event) => setFilter('issue', event.target.value)}
              >
                {ISSUE_OPTIONS.map(([value, label]) => (
                  <option key={value || 'any'} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Blockers' htmlFor='review-blocker-filter'>
              <Select
                id='review-blocker-filter'
                value={filters.has_blockers}
                onChange={(event) =>
                  setFilter('has_blockers', event.target.value)
                }
              >
                <option value=''>Any</option>
                <option value='true'>Has blockers</option>
                <option value='false'>No blockers</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Source' htmlFor='review-source-filter'>
              <Input
                id='review-source-filter'
                value={filters.source}
                placeholder='lcsd'
                onChange={(event) => setFilter('source', event.target.value)}
              />
            </AdminFilterField>
            <AdminFilterField label='Name' htmlFor='review-name-filter'>
              <Input
                id='review-name-filter'
                value={filters.q}
                onChange={(event) => setFilter('q', event.target.value)}
              />
            </AdminFilterField>
            <AdminFilterField label='Sort' htmlFor='review-sort'>
              <Select
                id='review-sort'
                value={filters.sort}
                onChange={(event) =>
                  setFilter(
                    'sort',
                    event.target.value === 'last_imported_at'
                      ? 'last_imported_at'
                      : 'name'
                  )
                }
              >
                <option value='name'>Name</option>
                <option value='last_imported_at'>Recently imported</option>
              </Select>
            </AdminFilterField>
          </AdminFilterBar>
        }
        toolbar={
          <div className='mb-3 space-y-3'>
            {notice ? (
              <StatusBanner variant='info' title='Bulk result'>
                {notice}
              </StatusBanner>
            ) : null}
            {error ? (
              <StatusBanner variant='error' title='Review queue'>
                {error}
              </StatusBanner>
            ) : null}
            <div className='flex flex-wrap items-center gap-2'>
              <Button
                type='button'
                onClick={() => void runBulk('approve')}
                disabled={isSaving || selected.size === 0}
                loading={activeBulk === 'approve'}
                loadingLabel='Saving…'
              >
                Approve
              </Button>
              <Button
                type='button'
                variant='secondary'
                onClick={() => void runBulk('reject')}
                disabled={isSaving || selected.size === 0}
                loading={activeBulk === 'reject'}
                loadingLabel='Saving…'
              >
                Reject
              </Button>
              <Button
                type='button'
                variant='secondary'
                onClick={() => void runBulk('reopen')}
                disabled={isSaving || selected.size === 0}
                loading={activeBulk === 'reopen'}
                loadingLabel='Saving…'
              >
                Reopen
              </Button>
              <Button
                type='button'
                variant='secondary'
                onClick={() => setShowFields(true)}
                disabled={selected.size === 0}
              >
                Apply properties
              </Button>
              <label className='flex items-center gap-2 text-sm text-slate-700'>
                <input
                  type='checkbox'
                  checked={force}
                  onChange={(event) => setForce(event.target.checked)}
                />
                Release even when details are missing
              </label>
            </div>
          </div>
        }
        leadingHead={
          <input
            type='checkbox'
            aria-label='Select all rows'
            checked={allSelected}
            onClick={(event) => {
              event.stopPropagation();
            }}
            onChange={(event) => {
              event.stopPropagation();
              const keys = items.map((item) => item.id);
              const isChecked = event.target.checked;
              setSelected((prev) => {
                const next = new Set(prev);
                keys.forEach((key) => {
                  if (isChecked) {
                    next.add(key);
                  } else {
                    next.delete(key);
                  }
                });
                return next;
              });
            }}
          />
        }
        renderLeading={(item) => (
          <input
            type='checkbox'
            aria-label='Select row'
            checked={selected.has(item.id)}
            onClick={(event) => {
              event.stopPropagation();
            }}
            onChange={(event) => {
              event.stopPropagation();
              setSelected((prev) => {
                const next = new Set(prev);
                if (next.has(item.id)) {
                  next.delete(item.id);
                } else {
                  next.add(item.id);
                }
                return next;
              });
            }}
          />
        )}
        head={
          <>
            <AdminDataTableHeadCell>Name</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Source
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Review
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Missing
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Complete
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <span className='font-medium'>{item.name}</span>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {item.source || '—'}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <StatusBadge status={item.review_status.replaceAll('_', ' ')} />
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {issueSummary(item)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {`${Math.round(item.completeness * 100)}%`}
            </AdminDataTableCell>
          </>
        )}
      />
      <ConfirmDialog
        open={showFields}
        title='Apply properties'
        message='Only the ticked fields are written. Empty text clears that field. Manager id cannot be cleared.'
        confirmLabel='Apply to selected'
        cancelLabel='Cancel'
        confirmLoading={activeBulk === 'set_fields'}
        confirmDisabled={isSaving}
        onConfirm={() => {
          const form = document.getElementById(BULK_FIELDS_FORM_ID);
          if (form instanceof HTMLFormElement) {
            form.requestSubmit();
          }
        }}
        onCancel={() => setShowFields(false)}
      >
        {error ? <p className='mb-3 text-sm text-red-600'>{error}</p> : null}
        <BulkFieldsDialog
          isSaving={isSaving}
          onInvalid={(message) => setError(message)}
          onApply={(fields) => {
            if (Object.keys(fields).length === 0) {
              setError('Tick at least one property.');
              return;
            }
            void runBulk('set_fields', fields);
          }}
        />
      </ConfirmDialog>
    </div>
  );
}
