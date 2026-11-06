'use client';

import { useState } from 'react';

import {
  DataQualityPanel,
  QualityFilters,
  QualitySelect,
  QualityText,
  STATUS_FILTERS,
} from '@/components/admin/data-quality/data-quality-panel';
import { ReviewQueueScopeNote, sweepLimitNote } from '@/components/admin/data-quality/sweep-shared';
import { CascadingAreaSelect } from '@/components/ui/cascading-area-select';
import { AdminEditorPanel } from '@/components/ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '@/components/ui/admin-field-grid';
import {
  adminTableText,
  AdminTableNumber,
  formatAdminTableLabel,
  formatAdminTablePercent,
} from '@/components/ui/admin-table-value';
import { ClosedLocationMark } from '@/components/shared/closed-location-mark';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useDataQualityQueue } from '@/hooks/use-data-quality-queue';
import { useGeographicAreas } from '@/hooks/use-geographic-areas';
import { useOrganizationScope } from '@/hooks/use-organization-scope';
import { adminTabLabel, formatAdminPageName } from '@/lib/admin-page-name';
import { googleMapsPinUrl } from '@/lib/location-maps';
import { isLocationClosed, locationStatusLabel } from '@/lib/location-status';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import {
  decideLocationFix,
  decideLocationFixesBulk,
  getLocationFix,
  getLocationFixSettings,
  getLocationFixSummary,
  listLocationFixes,
  scanLocationFixes,
  updateLocationFixSettings,
  type LocationFixProposal,
  type LocationFixSettings,
} from '@/lib/api-client-data-quality';

const PAGE_NAME = formatAdminPageName('Data quality', adminTabLabel.locations);
const KINDS = [
  ['', 'Any kind'],
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
const RECORDS = [
  ['', 'Any record'],
  ['organization', 'Organizations'],
  ['activity', 'Activities'],
  ['location', 'Locations'],
] as const;

function candidateLinkLabel(candidate: {
  address?: string | null;
  status?: string | null;
}): string {
  const place = candidate.address || 'venue';
  const closed = isLocationClosed(candidate.status)
    ? locationStatusLabel(candidate.status)
    : null;
  return closed ? `Link ${place} (${closed})` : `Link ${place}`;
}

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

type LocationSummary = Awaited<ReturnType<typeof getLocationFixSummary>>;
type LocationScan = Awaited<ReturnType<typeof scanLocationFixes>>;

function optionList(values: readonly string[], anyLabel: string): [string, string][] {
  return [['', anyLabel], ...values.map((value) => [value, value] as [string, string])];
}

function scanNotice(result: LocationScan): string {
  const scanned = result.total_entities == null ? '' : ` Scanned ${result.total_entities} entities.`;
  const lookedUp = result.queued_for_lookup ? ` Queued ${result.queued_for_lookup} pin lookups.` : '';
  const warning = result.error ? ` ${result.error}` : '';
  return `Created ${result.created}, updated ${result.updated}, skipped ${result.skipped}, cleared ${result.cleared}, linked ${result.auto_applied}, queued ${result.queued_for_model}.${scanned}${lookedUp}${sweepLimitNote(result.truncated)}${warning}`;
}

export function LocationsPanel() {
  const { openWorkspace } = useOrganizationScope();
  const areas = useGeographicAreas();
  const [address, setAddress] = useState('');
  const [areaId, setAreaId] = useState('');
  const [pinLat, setPinLat] = useState('');
  const [pinLng, setPinLng] = useState('');
  const [appliedProposalKey, setAppliedProposalKey] = useState<string | null>(null);
  const queue = useDataQualityQueue<
    LocationFixProposal,
    LocationFilters,
    LocationSummary,
    LocationFixSettings
  >({
    queryKey: adminQueryKeys.locationFixes(),
    paramName: 'location-fix',
    defaultFilters: DEFAULT_FILTERS,
    debounceKeys: ['q'],
    errorPrefix: 'Failed to load location fixes',
    selectionFields: ['q', 'entity_type', 'kind', 'source', 'grade', 'status'],
    sweepTimeout: true,
    fetchPage: ({ cursor, limit, orgId, q, entity_type, kind, source, grade, status }) =>
      listLocationFixes({
        cursor,
        limit,
        q: q || undefined,
        entity_type: entity_type || undefined,
        kind: kind || undefined,
        source: source || undefined,
        grade: grade || undefined,
        status: status || undefined,
        org_id: orgId || undefined,
      }),
    getOne: getLocationFix,
    loadSummary: getLocationFixSummary,
    loadSettings: getLocationFixSettings,
    pendingCount: (summary) => summary?.by_status.pending ?? 0,
    activeRun: (summary) => {
      const run = summary?.active_run;
      if (!run) return null;
      return { status: run.status, batches_done: run.batches_done, batches_total: run.batches_total };
    },
    scan: ({ reviewScope, filters, orgId }) =>
      scanLocationFixes({
        entity_type: filters.entity_type || undefined,
        q: filters.q || undefined,
        org_id: orgId || undefined,
        review_scope: reviewScope,
      }),
    formatScan: (result) => scanNotice(result as LocationScan),
    decide: (item, action, extra) => {
      const lat = Number(pinLat);
      const lng = Number(pinLng);
      return decideLocationFix(item.id, {
        action,
        ...(extra?.targetLocationId ? { target_location_id: extra.targetLocationId } : {}),
        ...(item.kind === 'create_location' && action === 'apply' ? { address, area_id: areaId } : {}),
        ...(item.kind === 'update_location' &&
        action === 'apply' &&
        pinLat.trim() &&
        pinLng.trim() &&
        Number.isFinite(lat) &&
        Number.isFinite(lng)
          ? { lat, lng }
          : {}),
      });
    },
    bulk: ({ action, all, ids, filters, orgId }) =>
      decideLocationFixesBulk(
        all
          ? {
              action,
              entity_type: filters.entity_type || undefined,
              kind: filters.kind || undefined,
              source: filters.source || undefined,
              grade: filters.grade || undefined,
              q: filters.q || undefined,
              org_id: orgId || undefined,
            }
          : { action, ids }
      ),
    appliedNotice: 'Location updated.',
    dismissedNotice: 'Proposal dismissed.',
    decideError: 'Could not update the location.',
    emptySelection: 'Select at least one location.',
    budget: {
      readLimit: (settings) => settings.monthly_cost_limit_usd,
      readMonthCost: (summary) => summary?.month_cost_usd ?? 0,
      save: (monthly) => updateLocationFixSettings({ monthly_cost_limit_usd: monthly }),
      savedNotice: 'Location budget saved.',
      saveError: 'Could not save the budget.',
    },
  });
  const open = queue.open;
  const proposalKey = [
    open?.id ?? '',
    open?.kind ?? '',
    open?.proposed_location?.address ?? '',
    open?.proposed_location?.area_id ?? '',
    open?.proposed_location?.lat ?? '',
    open?.proposed_location?.lng ?? '',
  ].join('\0');
  if (proposalKey !== appliedProposalKey) {
    setAppliedProposalKey(proposalKey);
    if (open?.kind === 'create_location') {
      setAddress(open.proposed_location?.address ?? '');
      setAreaId(open.proposed_location?.area_id ?? '');
    }
    if (open?.kind === 'update_location') {
      const lat = open.proposed_location?.lat;
      const lng = open.proposed_location?.lng;
      setPinLat(lat == null ? '' : String(lat));
      setPinLng(lng == null ? '' : String(lng));
    }
  }
  const filters = queue.list.filters;
  const place = open?.proposed_location;

  async function lookUp(provider: 'nominatim' | 'google') {
    await queue.runScan(
      provider,
      () =>
        scanLocationFixes({
          entity_type: 'location',
          q: filters.q || undefined,
          org_id: queue.organization || undefined,
          review_scope: 'pending_review',
          lookup: provider,
        }),
      (result) => {
        const scan = result as LocationScan;
        const stopped = scan.truncated ? ' Scan stopped at the limit; run it again to continue.' : '';
        const warning = scan.error ? ` ${scan.error}` : '';
        return `Queued ${scan.queued_for_lookup ?? 0} pin lookups.${stopped}${warning}`;
      },
      { failure: 'Lookup failed.' }
    );
  }

  return (
    <DataQualityPanel
      pageName={PAGE_NAME}
      noticeTitle='Locations'
      queue={queue}
      scope={
        queue.organization ? (
          <ReviewQueueScopeNote onClear={() => void queue.setOrganization(null)} />
        ) : null
      }
      getLabel={(item) => item.entity_name || item.current_label}
      middleColumnCount={6}
      emptyLabel='No locations match these filters. Sweep pending or Sweep all orgs to find some.'
      budgetDescription='Category checks are not counted.'
      budgetInputId='location-fix-budget'
      extraActions={
        <>
          <Button
            type='button'
            variant='secondary'
            onClick={() => void lookUp('nominatim')}
            loading={queue.scanningScope === 'nominatim'}
            loadingLabel='Looking up…'
            disabled={queue.sweepBusy}
          >
            Look up pins
          </Button>
          <Button
            type='button'
            variant='secondary'
            onClick={() => void lookUp('google')}
            loading={queue.scanningScope === 'google'}
            loadingLabel='Looking up…'
            disabled={queue.sweepBusy || !queue.summary?.google_places_configured}
          >
            Look up with Google
          </Button>
        </>
      }
      filters={
        <QualityFilters>
          <QualityText id='location-fix-q' label='Name' value={filters.q} onChange={(value) => queue.list.setFilter('q', value)} />
          <QualitySelect id='location-fix-entity' label='Record' value={filters.entity_type} onChange={(value) => queue.list.setFilter('entity_type', value)} options={RECORDS} />
          <QualitySelect id='location-fix-kind' label='Kind' value={filters.kind} onChange={(value) => queue.list.setFilter('kind', value)} options={KINDS} />
          <QualitySelect id='location-fix-source' label='Source' value={filters.source} onChange={(value) => queue.list.setFilter('source', value)} options={optionList(SOURCES, 'Any source')} />
          <QualitySelect id='location-fix-grade' label='Grade' value={filters.grade} onChange={(value) => queue.list.setFilter('grade', value)} options={optionList(GRADES, 'Any grade')} />
          <QualitySelect id='location-fix-status' label='Status' value={filters.status} onChange={(value) => queue.list.setFilter('status', value)} options={STATUS_FILTERS} />
        </QualityFilters>
      }
      columns={[
        {
          header: 'Record',
          cell: (item) => (
            <span className='inline-flex items-center'>
              {item.entity_name || formatAdminTableLabel(item.entity_type)}
              {item.entity_type === 'location' ? (
                <ClosedLocationMark status={item.venue_status ?? ''} />
              ) : null}
            </span>
          ),
        },
        { header: 'Current', cell: (item) => adminTableText(item.current_label) },
        {
          header: 'Proposed',
          cell: (item) => (
            <span className='inline-flex items-center'>
              {adminTableText(item.proposed_label)}
              {item.entity_type === 'location' ? null : (
                <ClosedLocationMark status={item.venue_status ?? ''} />
              )}
            </span>
          ),
        },
        { header: 'Source', priority: 'secondary', cell: (item) => adminTableText(item.source) },
        {
          header: 'Confidence',
          priority: 'secondary',
          empty: (item) => item.confidence == null,
          cell: (item) => <AdminTableNumber>{formatAdminTablePercent(item.confidence)}</AdminTableNumber>,
        },
        {
          header: 'Lookup',
          priority: 'tertiary',
          cell: (item) => adminTableText(item.proposed_location?.lookup?.grade),
        },
      ]}
      detail={
        open && open.status === 'pending' ? (
          <AdminEditorPanel>
            {open.rationale ? <p className='text-sm text-ink-700'>{open.rationale}</p> : null}
            {place?.register?.name ? (
              <p className='text-sm text-ink-700'>
                Register {place.register.name}
                {place.register.name_similarity == null ? '' : ` (${place.register.name_similarity})`}
              </p>
            ) : null}
            {place?.lookup?.grade ? (
              <p className='text-sm text-ink-700'>
                Lookup {place.lookup.grade}
                {place.lookup.display_name ? `: ${place.lookup.display_name}` : ''}
              </p>
            ) : null}
            {place?.lookup?.district_consistent === false ? (
              <p className='text-sm text-ink-700'>Pin is outside this district.</p>
            ) : null}
            {place?.lat != null && place?.lng != null ? (
              <a
                className='text-sm underline'
                href={googleMapsPinUrl(place.lat, place.lng)}
                target='_blank'
                rel='noreferrer'
              >
                Open in Google Maps
              </a>
            ) : null}
            {place?.candidates?.length ? (
              <div className='flex flex-col items-start gap-2'>
                {place.candidates.map((candidate) => (
                  <Button
                    key={candidate.location_id}
                    type='button'
                    variant='secondary'
                    onClick={() =>
                      void queue.decide(open, 'apply', {
                        targetLocationId: candidate.location_id,
                        activeId: `${open.id}:${candidate.location_id}`,
                      })
                    }
                    loading={queue.activeId === `${open.id}:${candidate.location_id}`}
                    loadingLabel='Saving…'
                  >
                    {candidateLinkLabel(candidate)}
                  </Button>
                ))}
              </div>
            ) : null}
            {open.kind === 'create_location' ? (
              <AdminFieldGrid columns={1}>
                <AdminField label='Address' htmlFor='location-fix-address'>
                  <Input id='location-fix-address' value={address} onChange={(event) => setAddress(event.target.value)} />
                </AdminField>
                <AdminField label='Area' htmlFor='location-fix-area'>
                  <CascadingAreaSelect tree={areas.tree} value={areaId} onChange={(next) => setAreaId(next)} />
                </AdminField>
              </AdminFieldGrid>
            ) : null}
            {open.kind === 'update_location' ? (
              <AdminFieldGrid columns={2}>
                <AdminField label='Latitude' htmlFor='location-fix-lat'>
                  <Input id='location-fix-lat' inputMode='decimal' value={pinLat} onChange={(event) => setPinLat(event.target.value)} />
                </AdminField>
                <AdminField label='Longitude' htmlFor='location-fix-lng'>
                  <Input id='location-fix-lng' inputMode='decimal' value={pinLng} onChange={(event) => setPinLng(event.target.value)} />
                </AdminField>
              </AdminFieldGrid>
            ) : null}
            <div className='flex gap-2'>
              {open.kind === 'unresolved' ? (
                <Button type='button' variant='secondary' onClick={() => openWorkspace(open.org_id, 'locations')}>
                  {open.entity_type === 'location' ? 'Edit location' : 'Create a location'}
                </Button>
              ) : (
                <Button
                  type='button'
                  onClick={() => void queue.decide(open, 'apply')}
                  loading={queue.activeId === open.id}
                  loadingLabel='Saving…'
                >
                  Apply
                </Button>
              )}
              <Button type='button' variant='secondary' onClick={() => void queue.decide(open, 'dismiss')}>
                Dismiss
              </Button>
            </div>
          </AdminEditorPanel>
        ) : null
      }
    />
  );
}
