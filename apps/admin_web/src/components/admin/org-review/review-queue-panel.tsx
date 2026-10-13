'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryState } from 'nuqs';

import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { useGeographicAreas } from '../../../hooks/use-geographic-areas';
import { useOrganizationScope } from '../../../hooks/use-organization-scope';
import { formatAdminPageName } from '../../../lib/admin-page-name';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import {
  CATALOG_MAP_ORG_CAP,
  CATALOG_MAP_PAGE_CAP,
  CATALOG_MAP_PAGE_SIZE,
  organizationsWithoutMapPins,
  pinsForOrganizations,
} from '../../../lib/catalog-map-pins';
import { neighbourhoodFilterOptions } from '../../../lib/neighbourhood-options';
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
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import {
  adminTableText,
  AdminTableId,
  AdminTableName,
  AdminTableNumber,
  formatAdminTableLabel,
  formatAdminTablePercent,
} from '../../ui/admin-table-value';
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
import { NeighbourhoodFilter } from './neighbourhood-filter';

const PAGE_NAME = formatAdminPageName('Catalog');

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
  changed: string;
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
  changed: '',
  sort: 'name',
};

function reviewChanged(
  value: string
): 'unchanged' | 'changed' | undefined {
  if (value === 'unchanged' || value === 'changed') {
    return value;
  }
  return undefined;
}

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
    changed: reviewChanged(filters.changed),
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
    limit: CATALOG_MAP_PAGE_SIZE,
    maxLimit: CATALOG_MAP_PAGE_SIZE,
    autoPageCap: CATALOG_MAP_PAGE_CAP,
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
  const [viewParam, setViewParam] = useQueryState('view');
  const view = viewParam === 'map' ? 'map' : 'table';
  const [mapMounted, setMapMounted] = useState(view === 'map');
  const setView = useCallback(
    (next: 'table' | 'map') => {
      if (next === 'map') {
        setMapMounted(true);
      }
      void setViewParam(next === 'map' ? 'map' : null);
    },
    [setViewParam]
  );
  useEffect(() => {
    if (view === 'map') {
      setMapMounted(true);
    }
  }, [view]);
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
    filters.changed,
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
    filters.changed,
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
      setForce(false);
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
          <AdminFilterBar>
            <AdminFilterField>
              <Select
                id='review-status-filter'
                aria-label='Review'
                value={filters.review_status}
                onChange={(event) =>
                  setFilter('review_status', event.target.value)
                }
              >
                <option value=''>Any review</option>
                <option value='pending_review'>Pending review</option>
                <option value='approved'>Approved</option>
                <option value='rejected'>Rejected</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField>
              <Select
                id='review-issue-filter'
                aria-label='Missing detail'
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
            <AdminFilterField>
              <Select
                id='review-changed-filter'
                aria-label='Catalog version'
                value={filters.changed}
                onChange={(event) => setFilter('changed', event.target.value)}
              >
                <option value=''>Any catalog version</option>
                <option value='unchanged'>Version 1</option>
                <option value='changed'>Later version</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField>
              <Select
                id='review-blocker-filter'
                aria-label='Blockers'
                value={filters.has_blockers}
                onChange={(event) =>
                  setFilter('has_blockers', event.target.value)
                }
              >
                <option value=''>Any blockers</option>
                <option value='true'>Has blockers</option>
                <option value='false'>No blockers</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField>
              <Input
                id='review-source-filter'
                aria-label='Source'
                value={filters.source}
                placeholder='Source'
                onChange={(event) => setFilter('source', event.target.value)}
              />
            </AdminFilterField>
            <AdminFilterField>
              <NeighbourhoodFilter
                id='review-neighbourhood-filter'
                value={filters.area_id}
                options={neighbourhoodFilterOptions(areas.tree)}
                onChange={(areaId) => setFilter('area_id', areaId)}
              />
            </AdminFilterField>
            <AdminFilterField>
              <Input
                id='review-name-filter'
                aria-label='Name'
                value={filters.q}
                placeholder='Name'
                onChange={(event) => setFilter('q', event.target.value)}
              />
            </AdminFilterField>
            <AdminFilterField>
              <Select
                id='review-sort'
                aria-label='Sort'
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
      <h2 className='sr-only'>{PAGE_NAME}</h2>
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
      {jobParam ? (
        <p className='text-sm text-slate-600'>
          Filtered to this import.{' '}
          <button
            type='button'
            className='underline'
            onClick={() => {
              void setJobParam(null);
            }}
          >
            Show all
          </button>
        </p>
      ) : null}
      {notice ? <StatusBanner kind='info'>{notice}</StatusBanner> : null}
      {error && !showFields ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
      {view === 'map' ? filterBar : null}
      <div className={view === 'map' ? undefined : 'hidden'}>
        {mapMounted ? (
        <Card>
          <CatalogOrgMap
            pins={mapPins}
            missingPinCount={missingPinCount}
            truncated={mapList.truncated}
            loadingMore={
              mapPins.length > 0 &&
              mapList.hasMore &&
              !mapList.truncated &&
              !mapList.error
            }
            isLoading={mapList.isLoading || mapList.isLoadingMore}
            active={view === 'map'}
            error={mapList.error}
            orgCap={CATALOG_MAP_ORG_CAP}
          />
        </Card>
        ) : null}
      </div>
      {view === 'table' ? (
      <ResourceTableShell
        ariaLabel={PAGE_NAME}
        rows={items}
        getLabel={(item) => item.name || `organization ${item.id}`}
        middleColumnCount={9}
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
        actions={
          <>
            <AdminCreateButton
              label='New organization'
              onClick={() => {
                void scope.openWorkspace('new');
              }}
            />
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
            <Button
              type='button'
              variant={force ? 'primary' : 'secondary'}
              aria-pressed={force}
              className='h-auto min-h-10 whitespace-normal py-2 text-left sm:min-h-9'
              onClick={() => setForce((current) => !current)}
            >
              Release even when details are missing
            </Button>
          </>
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
              Email
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Phone
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Manager
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
              <AdminTableName>{item.name}</AdminTableName>
              <AdminDataTableCellMeta until='secondary' label='Source'>
                {adminTableText(item.source)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary'>
                <StatusBadge status={formatAdminTableLabel(item.review_status)} />
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary' label='Email'>
                {adminTableText(item.email)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary' label='Phone'>
                {adminTableText(item.phone_number)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary' label='Manager' empty={!item.manager_id}>
                <AdminTableId>{item.manager_id}</AdminTableId>
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='tertiary' label='Import job' empty={!item.import_job_id}>
                <AdminTableId>{item.import_job_id}</AdminTableId>
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='tertiary' label='Missing'>
                {issueSummary(item)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='tertiary'>
                <AdminTableNumber>{formatAdminTablePercent(item.completeness)}</AdminTableNumber>
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {adminTableText(item.source)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <StatusBadge status={formatAdminTableLabel(item.review_status)} />
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {adminTableText(item.email)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {adminTableText(item.phone_number)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <AdminTableId>{item.manager_id}</AdminTableId>
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <AdminTableId>{item.import_job_id}</AdminTableId>
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {issueSummary(item)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <AdminTableNumber>{formatAdminTablePercent(item.completeness)}</AdminTableNumber>
            </AdminDataTableCell>
          </>
        )}
      />
      ) : null}
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
