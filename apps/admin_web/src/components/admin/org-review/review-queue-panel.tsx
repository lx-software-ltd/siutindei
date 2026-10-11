'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryState } from 'nuqs';

import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { useGeographicAreas } from '../../../hooks/use-geographic-areas';
import { useOrganizationScope } from '../../../hooks/use-organization-scope';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import {
  organizationsWithoutMapPins,
  pinsForOrganizations,
} from '../../../lib/catalog-map-pins';
import { neighbourhoodOptionGroups } from '../../../lib/neighbourhood-options';
import { ApiError } from '../../../lib/api-client';
import {
  bulkOrgReview,
  getOrgReviewSummary,
  listOrgReviews,
  type OrgReviewListItem,
  type OrgReviewSummary,
} from '../../../lib/api-client-org-review';
import { StatusBanner } from '../../status-banner';
import {
  AdminDataTableCell,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { Button } from '../../ui/button';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Input } from '../../ui/input';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { Select } from '../../ui/select';
import { StatusBadge } from '../../ui/status-badge';
import { AdminCreateButton } from '../../ui/admin-create-button';
import { AdminKpiCard } from '../../ui/admin-kpi-card';
import { AdminTabStrip } from '../../ui/admin-tab-strip';
import { Card } from '../../ui/card';
import { BULK_FIELDS_FORM_ID, BulkFieldsDialog } from './bulk-fields-dialog';
import { CatalogOrgMap } from './catalog-org-map';

const ISSUE_OPTIONS = [
  ['', 'Any issue'],
  ['missing_description', 'Missing description'],
  ['no_locations', 'No locations'],
  ['activity_no_location', 'Activity has no location'],
  ['no_activities', 'No activities'],
  ['missing_coordinates', 'Missing map pin'],
  ['missing_pricing', 'Missing price'],
  ['missing_schedule', 'Missing schedule'],
  ['pending_category', 'Pending category'],
  ['category_check_pending', 'Category check'],
  ['no_contact', 'No contact'],
  ['no_media', 'No photos'],
  ['source_attribution', 'Template or source line'],
  ['name_needs_cleanup', 'Name needs cleanup'],
  ['possible_duplicate', 'Possible duplicate'],
];

type BulkAction = 'approve' | 'reject' | 'reopen' | 'set_fields';

interface ReviewQueueFilters {
  review_status: string;
  source: string;
  issue: string;
  has_blockers: string;
  q: string;
  import_job_id: string;
  area_id: string;
  sort: 'name' | 'last_imported_at';
}

const DEFAULT_REVIEW_FILTERS: ReviewQueueFilters = {
  review_status: '',
  source: '',
  issue: '',
  has_blockers: '',
  q: '',
  import_job_id: '',
  area_id: '',
  sort: 'name',
};

function reviewListParams(filters: ReviewQueueFilters) {
  return {
    review_status: filters.review_status || undefined,
    source: filters.source || undefined,
    issue: filters.issue || undefined,
    has_blockers:
      filters.has_blockers === '' ? undefined : filters.has_blockers === 'true',
    q: filters.q || undefined,
    import_job_id: filters.import_job_id || undefined,
    area_id: filters.area_id || undefined,
    sort:
      filters.sort === 'last_imported_at'
        ? ('last_imported_at' as const)
        : undefined,
  };
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

export function CatalogPanel() {
  const scope = useOrganizationScope();
  const [jobParam, setJobParam] = useQueryState('job');
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
    fetcher: async ({ cursor, limit, ...filters }) => {
      const page = await listOrgReviews({
        ...reviewListParams(filters),
        cursor: cursor ?? undefined,
        limit,
      });
      return {
        items: page.items,
        nextCursor: page.next_cursor ?? null,
      };
    },
  });
  const mapList = usePaginatedList<OrgReviewListItem, ReviewQueueFilters>({
    queryKey: adminQueryKeys.orgReviewMap(),
    defaultFilters,
    limit: 50,
    fetchOnMount: false,
    fetchAll: true,
    errorPrefix: 'Failed to load the map',
    fetcher: async ({ cursor, limit, ...filters }) => {
      const page = await listOrgReviews({
        ...reviewListParams(filters),
        include: 'locations',
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
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [force, setForce] = useState(false);
  const [showFields, setShowFields] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [activeBulk, setActiveBulk] = useState<BulkAction | null>(null);
  const [view, setView] = useState<'table' | 'map'>('table');
  const areas = useGeographicAreas();
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
    filters.area_id,
    filters.sort,
  ]);

  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const textFiltersRef = useRef({ q: filters.q, source: filters.source });
  const mapRefetchRef = useRef(mapList.refetch);
  mapRefetchRef.current = mapList.refetch;
  useEffect(() => {
    const textChanged =
      textFiltersRef.current.q !== filters.q ||
      textFiltersRef.current.source !== filters.source;
    textFiltersRef.current = { q: filters.q, source: filters.source };
    if (view !== 'map') {
      return;
    }
    const handle = window.setTimeout(() => {
      void mapRefetchRef.current(filtersRef.current);
    }, textChanged ? 300 : 0);
    return () => {
      window.clearTimeout(handle);
    };
  }, [
    view,
    filters.review_status,
    filters.source,
    filters.issue,
    filters.has_blockers,
    filters.q,
    filters.import_job_id,
    filters.area_id,
    filters.sort,
  ]);

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
    void scope.openWorkspace(orgId);
  }

  const pendingCount = summary?.by_review_status.pending_review ?? 0;
  const isSaving = activeBulk !== null;
  const allSelected =
    items.length > 0 && items.every((item) => selected.has(item.id));
  const mapPins = pinsForOrganizations(mapList.items);
  const missingPinCount = organizationsWithoutMapPins(mapList.items);

  const filterBar = (
          <AdminFilterBar
            trailing={
              <>
                <AdminCreateButton
                  label='New organization'
                  onClick={() => {
                    void scope.openWorkspace('new');
                  }}
                />
                {jobParam ? (
                  // Leaves the import-job URL scope. This is not a filter
                  // field, so it is the one Clear control on this bar.
                  <Button
                    type='button'
                    variant='secondary'
                    onClick={() => {
                      void setJobParam(null);
                    }}
                  >
                    Clear import filter
                  </Button>
                ) : null}
              </>
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
            <AdminFilterField label='Neighbourhood' htmlFor='review-neighbourhood-filter'>
              <Select
                id='review-neighbourhood-filter'
                value={filters.area_id}
                onChange={(event) => setFilter('area_id', event.target.value)}
              >
                <option value=''>All neighbourhoods</option>
                {neighbourhoodOptionGroups(areas.tree).map(([group, options]) => (
                  <optgroup
                    key={group || 'neighbourhood'}
                    label={group || 'Neighbourhood'}
                  >
                    {options.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Select>
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
  );

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>Catalog</h2>
      <div className='grid gap-3 sm:grid-cols-3'>
        <AdminKpiCard label='Pending review' value={pendingCount} />
        <AdminKpiCard
          label='With missing details'
          value={summary?.with_blockers ?? 0}
        />
        <AdminKpiCard
          label='Approved'
          value={summary?.by_review_status.approved ?? 0}
        />
      </div>
      <AdminTabStrip
        aria-label='Catalog view'
        activeKey={view}
        onChange={setView}
        items={[
          { key: 'table', label: 'Table' },
          { key: 'map', label: 'Map' },
        ]}
      />
      {view === 'map' ? (
        <Card>
          {filterBar}
          <CatalogOrgMap
            pins={mapPins}
            missingPinCount={missingPinCount}
            truncated={mapList.hasMore && !mapList.isLoading && !mapList.isLoadingMore}
            isLoading={mapList.isLoading || mapList.isLoadingMore}
            error={mapList.error}
          />
        </Card>
      ) : (
      <ResourceTableShell
        ariaLabel='Catalog'
        rows={items}
        getLabel={(item) => item.name || `organization ${item.id}`}
        middleColumnCount={7}
        hasActions={false}
        isLoading={isLoading}
        isLoadingMore={isLoadingMore}
        hasMore={hasMore}
        onLoadMore={() => {
          void loadMore();
        }}
        error={list.error}
        emptyLabel='No organizations match these filters.'
        isExpanded={() => false}
        onToggle={openOrganization}
        detail={null}
        filters={filterBar}
        toolbar={
          <div className='mb-3 space-y-3'>
            {notice ? (
              <StatusBanner kind='info'>
                {notice}
              </StatusBanner>
            ) : null}
            {error ? (
              <StatusBanner kind='error'>
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
            <AdminDataTableHeadCell priority='secondary'>
              Contact
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Import job
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
            <AdminDataTableCell priority='secondary'>
              <span>{item.email || '—'}</span>
              <span className='block text-xs text-slate-500'>
                {item.phone_number || 'No phone'}
              </span>
              <span className='block text-xs text-slate-500'>
                {item.manager_id ? `Manager ${item.manager_id}` : 'No manager'}
              </span>
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {item.import_job_id || '—'}
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
      )}
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
        {error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
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
