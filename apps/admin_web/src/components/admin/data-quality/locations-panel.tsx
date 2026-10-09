'use client';

import { useQuery } from '@tanstack/react-query';
import { useQueryState } from 'nuqs';
import { useEffect, useRef, useState } from 'react';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { useOrganizationScope } from '../../../hooks/use-organization-scope';
import { useGeographicAreas } from '../../../hooks/use-geographic-areas';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { getAdminQueryClient } from '../../../lib/admin-query-client';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { ApiError } from '../../../lib/api-client';
import {
  decideLocationFix,
  decideLocationFixesBulk,
  exportLocationFixes,
  getLocationFix,
  getLocationFixSettings,
  getLocationFixSummary,
  listLocationFixes,
  scanLocationFixes,
  updateLocationFixSettings,
  type LocationFixProposal,
  type LocationFixSettings,
} from '../../../lib/api-client-data-quality';
import { StatusBanner } from '../../status-banner';
import { AdminDataTableCell, AdminDataTableHeadCell } from '../../ui/admin-data-table';
import { CascadingAreaSelect } from '../../ui/cascading-area-select';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '../../ui/admin-field-grid';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { Select } from '../../ui/select';

const KINDS = [
  ['link_existing', 'Link existing'],
  ['create_location', 'Create location'],
  ['update_location', 'Update location'],
  ['unresolved', 'Unresolved'],
] as const;

const SOURCES = [
  'rule:single_location',
  'rule:pricing_schedule',
  'rule:name_area',
  'rule:no_venue',
  'model',
  'rule:missing_coordinates',
  'rule:empty_address',
  'rule:pin_outside_area',
  'rule:open_data',
  'lookup:nominatim',
  'lookup:google',
] as const;

const GRADES = ['precise', 'street', 'coarse', 'miss', 'manual', 'not_looked_up'] as const;

interface LocationFilters {
  q: string;
  entity_type: string;
  kind: string;
  source: string;
  grade: string;
  status: string;
}

const DEFAULT_FILTERS: LocationFilters = {
  q: '',
  entity_type: '',
  kind: '',
  source: '',
  grade: '',
  status: 'pending',
};

export function LocationsPanel() {
  const [organization, setOrganization] = useQueryState('organization');
  const { openWorkspace } = useOrganizationScope();
  const orgIdRef = useRef(organization);
  orgIdRef.current = organization;
  const expanded = useExpandedRecord({ paramName: 'location-fix' });
  const areas = useGeographicAreas();
  const summaryQuery = useQuery({
    queryKey: [...adminQueryKeys.locationFixes(), 'summary'],
    queryFn: getLocationFixSummary,
    refetchInterval: (query) => {
      const status = query.state.data?.active_run?.status;
      return status === 'queued' || status === 'running' ? 3000 : false;
    },
  });
  const settingsQuery = useQuery({
    queryKey: [...adminQueryKeys.locationFixes(), 'settings'],
    queryFn: getLocationFixSettings,
  });
  const [draftLimit, setDraftLimit] = useState<string | null>(null);
  const settings = settingsQuery.data ?? null;
  const limitValue =
    draftLimit ??
    (settings ? String(settings.monthly_cost_limit_usd) : '');
  const list = usePaginatedList<LocationFixProposal, LocationFilters>({
    queryKey: [...adminQueryKeys.locationFixes(), organization ?? ''],
    defaultFilters: DEFAULT_FILTERS,
    debounceKeys: ['q'],
    errorPrefix: 'Failed to load location fixes',
    fetcher: async ({ cursor, limit, q, entity_type, kind, source, grade, status }) => {
      const page = await listLocationFixes({
        cursor: cursor ?? undefined,
        limit,
        q: q || undefined,
        entity_type: entity_type || undefined,
        kind: kind || undefined,
        source: source || undefined,
        grade: grade || undefined,
        status: status || undefined,
        org_id: orgIdRef.current || undefined,
      });
      return { items: page.items, nextCursor: page.next_cursor ?? null };
    },
  });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [scanningScope, setScanningScope] = useState<
    'pending_review' | 'all' | 'nominatim' | 'google' | null
  >(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectScope, setSelectScope] = useState<'none' | 'visible' | 'all'>(
    'none'
  );
  const [address, setAddress] = useState('');
  const [areaId, setAreaId] = useState('');
  const [pinLat, setPinLat] = useState('');
  const [pinLng, setPinLng] = useState('');
  const selectAllRef = useRef<HTMLInputElement>(null);
  const activeRun = summaryQuery.data?.active_run ?? null;
  const sweepBusy =
    scanningScope !== null ||
    activeRun?.status === 'queued' ||
    activeRun?.status === 'running';

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate =
        selectScope === 'visible' && list.hasMore;
    }
  }, [list.hasMore, selectScope]);

  useEffect(() => {
    setSelectScope('none');
    setSelected(new Set());
  }, [
    list.filters.q,
    list.filters.entity_type,
    list.filters.kind,
    list.filters.source,
    list.filters.grade,
    list.filters.status,
    organization,
  ]);

  useEffect(() => {
    if (selectScope !== 'visible') {
      return;
    }
    setSelected((current) => {
      let changed = false;
      const next = new Set(current);
      for (const item of list.items) {
        if (!next.has(item.id)) {
          next.add(item.id);
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [list.items, selectScope]);

  const listed = list.items.find((item) => item.id === expanded.expandedId) ?? null;
  const detailQuery = useQuery({
    queryKey: [...adminQueryKeys.locationFixes(), 'one', expanded.expandedId],
    queryFn: () => getLocationFix(expanded.expandedId as string),
    enabled: Boolean(expanded.expandedId) && !list.isLoading && listed === null,
  });
  const open = listed ?? detailQuery.data ?? null;

  const openProposalId = open?.id ?? '';
  const openProposalKind = open?.kind;
  const openProposalAddress = open?.proposed_location?.address ?? '';
  const openProposalArea = open?.proposed_location?.area_id ?? '';
  const openProposalLat = open?.proposed_location?.lat;
  const openProposalLng = open?.proposed_location?.lng;
  useEffect(() => {
    if (openProposalKind === 'create_location') {
      setAddress(openProposalAddress);
      setAreaId(openProposalArea);
    }
    if (openProposalKind === 'update_location') {
      setPinLat(openProposalLat == null ? '' : String(openProposalLat));
      setPinLng(openProposalLng == null ? '' : String(openProposalLng));
    }
  }, [
    openProposalId,
    openProposalKind,
    openProposalAddress,
    openProposalArea,
    openProposalLat,
    openProposalLng,
  ]);

  const pending = summaryQuery.data?.by_status.pending ?? 0;
  const progress =
    activeRun && (activeRun.status === 'queued' || activeRun.status === 'running')
      ? ` Sweep ${activeRun.batches_done} of ${activeRun.batches_total} batches.`
      : '';
  const summary = summaryQuery.data
    ? `${pending} pending.${progress}`
    : 'No pending locations.';

  async function refresh() {
    await getAdminQueryClient().invalidateQueries({
      queryKey: [...adminQueryKeys.locationFixes(), 'summary'],
    });
    await list.refetch();
  }

  async function sweep(reviewScope: 'pending_review' | 'all') {
    setScanningScope(reviewScope);
    setError('');
    setNotice('');
    try {
      const result = await scanLocationFixes({
        entity_type: list.filters.entity_type || undefined,
        q: list.filters.q || undefined,
        org_id: organization || undefined,
        review_scope: reviewScope,
      });
      const stopped = result.truncated
        ? ' Scan stopped at the limit; run it again to continue.'
        : '';
      const lookedUp = result.queued_for_lookup
        ? ` Queued ${result.queued_for_lookup} pin lookups.`
        : '';
      setNotice(
        `Created ${result.created}, updated ${result.updated}, skipped ${result.skipped}, cleared ${result.cleared}, linked ${result.auto_applied}, queued ${result.queued_for_model}.${lookedUp}${stopped}`
      );
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Scan failed.');
    } finally {
      setScanningScope(null);
    }
  }

  async function lookUp(provider: 'nominatim' | 'google') {
    setScanningScope(provider);
    setError('');
    setNotice('');
    try {
      const result = await scanLocationFixes({
        entity_type: 'location',
        q: list.filters.q || undefined,
        org_id: organization || undefined,
        review_scope: 'pending_review',
        lookup: provider,
      });
      const stopped = result.truncated
        ? ' Scan stopped at the limit; run it again to continue.'
        : '';
      setNotice(`Queued ${result.queued_for_lookup ?? 0} pin lookups.${stopped}`);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Lookup failed.');
    } finally {
      setScanningScope(null);
    }
  }

  async function exportCsv() {
    setError('');
    try {
      const csv = await exportLocationFixes({
        status: list.filters.status || undefined,
        entity_type: list.filters.entity_type || undefined,
        kind: list.filters.kind || undefined,
        source: list.filters.source || undefined,
        grade: list.filters.grade || undefined,
        q: list.filters.q || undefined,
        org_id: organization || undefined,
      });
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'location-fixes.csv';
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Export failed.');
    }
  }

  async function decide(
    item: LocationFixProposal,
    action: 'apply' | 'dismiss',
    targetLocationId?: string
  ) {
    setActiveId(targetLocationId ? `${item.id}:${targetLocationId}` : item.id);
    setError('');
    try {
      const lat = Number(pinLat);
      const lng = Number(pinLng);
      await decideLocationFix(item.id, {
        action,
        ...(targetLocationId ? { target_location_id: targetLocationId } : {}),
        ...(item.kind === 'create_location' && action === 'apply'
          ? { address, area_id: areaId }
          : {}),
        ...(item.kind === 'update_location' &&
        action === 'apply' &&
        pinLat.trim() &&
        pinLng.trim() &&
        Number.isFinite(lat) &&
        Number.isFinite(lng)
          ? { lat, lng }
          : {}),
      });
      setNotice(action === 'apply' ? 'Location updated.' : 'Proposal dismissed.');
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update the location.');
    } finally {
      setActiveId(null);
    }
  }

  async function bulk(action: 'apply' | 'dismiss') {
    if (selectScope !== 'all' && selected.size === 0) {
      setError('Select at least one location.');
      return;
    }
    setError('');
    try {
      const result = await decideLocationFixesBulk(
        selectScope === 'all'
          ? {
              action,
              entity_type: list.filters.entity_type || undefined,
              kind: list.filters.kind || undefined,
              source: list.filters.source || undefined,
              grade: list.filters.grade || undefined,
              q: list.filters.q || undefined,
              org_id: organization || undefined,
            }
          : { action, ids: Array.from(selected) }
      );
      setNotice(`Updated ${result.decided}. ${result.failed} failed.`);
      setSelected(new Set());
      setSelectScope('none');
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bulk update failed.');
    }
  }

  async function saveSettings() {
    const monthly = Number(limitValue);
    if (!Number.isFinite(monthly)) {
      setError('Enter a monthly limit.');
      return;
    }
    setError('');
    try {
      const saved = await updateLocationFixSettings({
        monthly_cost_limit_usd: monthly,
      });
      getAdminQueryClient().setQueryData<LocationFixSettings>(
        [...adminQueryKeys.locationFixes(), 'settings'],
        saved
      );
      setDraftLimit(null);
      setNotice('Location budget saved.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the budget.');
    }
  }

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>Locations</h2>
      {organization ? (
        <p className='text-sm text-slate-600'>
          Filtered to the organization from the review queue. Sweep pending
          only includes organizations still in review. Sweep all orgs includes
          this organization when it is already approved.{' '}
          <button
            type='button'
            className='underline'
            onClick={() => {
              void setOrganization(null);
            }}
          >
            Show all
          </button>
        </p>
      ) : null}
      {notice ? (
        <StatusBanner kind='info' title='Locations'>
          {notice}
        </StatusBanner>
      ) : null}
      {error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
      {selectScope === 'all' ? (
        <StatusBanner kind='info' title='Selection'>
          All matching records are selected, including rows not on this page.
        </StatusBanner>
      ) : null}
      <ResourceTableShell
        ariaLabel='Location fixes'
        toolbar={
          <div className='mb-3 flex flex-wrap items-end gap-2'>
            <p className='w-full text-sm text-slate-700'>{summary}</p>
            <Button
              type='button'
              onClick={() => void sweep('pending_review')}
              loading={scanningScope === 'pending_review'}
              loadingLabel='Scanning…'
              disabled={sweepBusy}
            >
              Sweep pending
            </Button>
            <Button
              type='button'
              onClick={() => void sweep('all')}
              loading={scanningScope === 'all'}
              loadingLabel='Scanning…'
              disabled={sweepBusy}
            >
              Sweep all orgs
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void bulk('apply')}
              disabled={selectScope !== 'all' && selected.size === 0}
            >
              Apply selected
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void bulk('dismiss')}
              disabled={selectScope !== 'all' && selected.size === 0}
            >
              Dismiss selected
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void lookUp('nominatim')}
              loading={scanningScope === 'nominatim'}
              loadingLabel='Looking up…'
              disabled={sweepBusy}
            >
              Look up pins
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void lookUp('google')}
              loading={scanningScope === 'google'}
              loadingLabel='Looking up…'
              disabled={sweepBusy || !summaryQuery.data?.google_places_configured}
            >
              Look up with Google
            </Button>
            <Button type='button' variant='secondary' onClick={() => void exportCsv()}>
              Export CSV
            </Button>
          </div>
        }
        rows={list.items}
        getLabel={(item) => item.entity_name || item.current_label}
        middleColumnCount={5}
        hasActions={false}
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={
          open && open.status === 'pending' ? (
            <AdminEditorPanel>
              {open.rationale ? (
                <p className='text-sm text-slate-700'>{open.rationale}</p>
              ) : null}
              {open.proposed_location?.register?.name ? (
                <p className='text-sm text-slate-700'>
                  Register {open.proposed_location.register.name}
                  {open.proposed_location.register.name_similarity == null
                    ? ''
                    : ` (${open.proposed_location.register.name_similarity})`}
                </p>
              ) : null}
              {open.proposed_location?.lookup?.grade ? (
                <p className='text-sm text-slate-700'>
                  Lookup {open.proposed_location.lookup.grade}
                  {open.proposed_location.lookup.display_name
                    ? `: ${open.proposed_location.lookup.display_name}`
                    : ''}
                </p>
              ) : null}
              {open.proposed_location?.lookup?.district_consistent === false ? (
                <p className='text-sm text-slate-700'>Pin is outside this district.</p>
              ) : null}
              {open.proposed_location?.lat != null && open.proposed_location?.lng != null ? (
                <a
                  className='text-sm underline'
                  href={`https://www.google.com/maps/search/?api=1&query=${open.proposed_location.lat},${open.proposed_location.lng}`}
                  target='_blank'
                  rel='noreferrer'
                >
                  Open in Google Maps
                </a>
              ) : null}
              {open.proposed_location?.candidates?.length ? (
                <div className='flex flex-col items-start gap-2'>
                  {open.proposed_location.candidates.map((candidate) => (
                    <Button
                      key={candidate.location_id}
                      type='button'
                      variant='secondary'
                      onClick={() => void decide(open, 'apply', candidate.location_id)}
                      loading={activeId === `${open.id}:${candidate.location_id}`}
                      loadingLabel='Saving…'
                    >
                      Link {candidate.address || 'venue'}
                    </Button>
                  ))}
                </div>
              ) : null}
              {open.kind === 'create_location' ? (
                <AdminFieldGrid columns={1}>
                  <AdminField label='Address' htmlFor='location-fix-address'>
                    <Input
                      id='location-fix-address'
                      value={address}
                      onChange={(event) => setAddress(event.target.value)}
                    />
                  </AdminField>
                  <AdminField label='Area' htmlFor='location-fix-area'>
                    <CascadingAreaSelect
                      tree={areas.tree}
                      value={areaId}
                      onChange={(next) => setAreaId(next)}
                    />
                  </AdminField>
                </AdminFieldGrid>
              ) : null}
              {open.kind === 'update_location' ? (
                <AdminFieldGrid columns={2}>
                  <AdminField label='Latitude' htmlFor='location-fix-lat'>
                    <Input
                      id='location-fix-lat'
                      inputMode='decimal'
                      value={pinLat}
                      onChange={(event) => setPinLat(event.target.value)}
                    />
                  </AdminField>
                  <AdminField label='Longitude' htmlFor='location-fix-lng'>
                    <Input
                      id='location-fix-lng'
                      inputMode='decimal'
                      value={pinLng}
                      onChange={(event) => setPinLng(event.target.value)}
                    />
                  </AdminField>
                </AdminFieldGrid>
              ) : null}
              <div className='flex gap-2'>
                {open.kind === 'unresolved' ? (
                  <Button
                    type='button'
                    variant='secondary'
                    onClick={() => openWorkspace(open.org_id, 'locations')}
                  >
                    {open.entity_type === 'location'
                      ? 'Edit location'
                      : 'Create a location'}
                  </Button>
                ) : (
                  <Button
                    type='button'
                    onClick={() => void decide(open, 'apply')}
                    loading={activeId === open.id}
                    loadingLabel='Saving…'
                  >
                    Apply
                  </Button>
                )}
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => void decide(open, 'dismiss')}
                >
                  Dismiss
                </Button>
              </div>
            </AdminEditorPanel>
          ) : null
        }
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={() => void list.loadMore()}
        error={list.error}
        emptyLabel='No locations match these filters. Sweep pending or Sweep all orgs to find some.'
        filters={
          <AdminFilterBar>
            <AdminFilterField label='Name' htmlFor='location-fix-q'>
              <Input
                id='location-fix-q'
                value={list.filters.q}
                onChange={(event) => list.setFilter('q', event.target.value)}
              />
            </AdminFilterField>
            <AdminFilterField label='Record' htmlFor='location-fix-entity'>
              <Select
                id='location-fix-entity'
                value={list.filters.entity_type}
                onChange={(event) => list.setFilter('entity_type', event.target.value)}
              >
                <option value=''>All records</option>
                <option value='organization'>Organizations</option>
                <option value='activity'>Activities</option>
                <option value='location'>Locations</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Kind' htmlFor='location-fix-kind'>
              <Select
                id='location-fix-kind'
                value={list.filters.kind}
                onChange={(event) => list.setFilter('kind', event.target.value)}
              >
                <option value=''>All kinds</option>
                {KINDS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Source' htmlFor='location-fix-source'>
              <Select
                id='location-fix-source'
                value={list.filters.source}
                onChange={(event) => list.setFilter('source', event.target.value)}
              >
                <option value=''>All sources</option>
                {SOURCES.map((source) => (
                  <option key={source} value={source}>
                    {source}
                  </option>
                ))}
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Grade' htmlFor='location-fix-grade'>
              <Select
                id='location-fix-grade'
                value={list.filters.grade}
                onChange={(event) => list.setFilter('grade', event.target.value)}
              >
                <option value=''>All grades</option>
                {GRADES.map((grade) => (
                  <option key={grade} value={grade}>
                    {grade}
                  </option>
                ))}
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Status' htmlFor='location-fix-status'>
              <Select
                id='location-fix-status'
                value={list.filters.status}
                onChange={(event) => list.setFilter('status', event.target.value)}
              >
                <option value='pending'>Pending</option>
                <option value='applied'>Applied</option>
                <option value='dismissed'>Dismissed</option>
              </Select>
            </AdminFilterField>
          </AdminFilterBar>
        }
        leadingHead={
          <input
            ref={selectAllRef}
            type='checkbox'
            aria-label={
              selectScope === 'all'
                ? 'Clear selection'
                : selectScope === 'visible' && list.hasMore
                  ? 'Select all matching rows'
                  : 'Select visible rows'
            }
            checked={selectScope === 'all' || selectScope === 'visible'}
            onChange={() => {
              if (selectScope === 'none') {
                setSelected(new Set(list.items.map((item) => item.id)));
                setSelectScope('visible');
                return;
              }
              if (selectScope === 'visible' && list.hasMore) {
                setSelectScope('all');
                return;
              }
              setSelected(new Set());
              setSelectScope('none');
            }}
          />
        }
        renderLeading={(item) => (
          <input
            type='checkbox'
            aria-label='Select row'
            checked={selectScope === 'all' || selected.has(item.id)}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => {
              setSelectScope('visible');
              setSelected((current) => {
                const next = new Set(current);
                if (event.target.checked) {
                  next.add(item.id);
                } else {
                  next.delete(item.id);
                }
                if (next.size === 0) {
                  setSelectScope('none');
                }
                return next;
              });
            }}
          />
        )}
        head={
          <>
            <AdminDataTableHeadCell>Record</AdminDataTableHeadCell>
            <AdminDataTableHeadCell>Current</AdminDataTableHeadCell>
            <AdminDataTableHeadCell>Proposed</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Source</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>Lookup</AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              {item.entity_name || item.entity_type}
            </AdminDataTableCell>
            <AdminDataTableCell>{item.current_label}</AdminDataTableCell>
            <AdminDataTableCell>{item.proposed_label}</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {item.source}
              {item.confidence == null ? '' : ` ${item.confidence}`}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {item.proposed_location?.lookup?.grade || ''}
            </AdminDataTableCell>
          </>
        )}
      />
      {settings ? (
        <div className='space-y-3 rounded-lg border border-slate-200 bg-white p-4'>
          <h3 className='text-sm font-medium text-slate-900'>Model budget</h3>
          <p className='text-sm text-slate-600'>
            This month {summaryQuery.data?.month_cost_usd ?? 0} of{' '}
            {settings.monthly_cost_limit_usd} USD. Category checks are not counted.
          </p>
          <AdminField label='Monthly limit (USD)' htmlFor='location-fix-budget'>
            <Input
              id='location-fix-budget'
              inputMode='decimal'
              value={limitValue}
              onChange={(event) => setDraftLimit(event.target.value)}
            />
          </AdminField>
          <Button type='button' variant='secondary' onClick={() => void saveSettings()}>
            Save budget
          </Button>
        </div>
      ) : null}
    </div>
  );
}
