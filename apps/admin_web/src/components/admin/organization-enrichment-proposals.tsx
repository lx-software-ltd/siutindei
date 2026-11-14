'use client';

import { useState } from 'react';

import { useActivityCategories } from '../../hooks/use-activity-categories';
import { useGeographicAreas } from '../../hooks/use-geographic-areas';
import type {
  EnrichmentBlocker,
  EnrichmentOverride,
  EnrichmentProposal,
  EnrichmentRead,
} from '../../lib/api-client-enrichment';
import { adminCurrencyOptions } from '../../lib/admin-currencies';
import { positiveSessions, visibleBlockers } from '../../lib/enrichment-overrides';
import { MAX_LISTING_AGE } from '../../lib/listing-age';
import { locationListLabel } from '../../lib/location-label';
import type { GeographicAreaNode } from '../../lib/api-client-user';
import { CascadingAreaSelect } from '../ui/cascading-area-select';
import { CascadingCategorySelect } from '../ui/cascading-category-select';
import {
  AdminDataTable,
  AdminDataTableBody,
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHead,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { AdminInlineError } from '../ui/admin-inline-error';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select } from '../ui/select';
import {
  pricingOptions,
} from '../shared/pricing/pricing-types';
import { StatusBadge } from '../ui/status-badge';
import {
  AdminTableName,
  AdminTableNumber,
  formatAdminTablePercent,
} from '../ui/admin-table-value';

function sameAreaName(node: GeographicAreaNode, name: string): boolean {
  const wanted = name.trim().toLowerCase();
  if (!wanted) {
    return false;
  }
  if (node.name.trim().toLowerCase() === wanted) {
    return true;
  }
  return Object.values(node.name_translations ?? {}).some(
    (value) => typeof value === 'string' && value.trim().toLowerCase() === wanted
  );
}

function containsArea(nodes: GeographicAreaNode[], id: string): boolean {
  return nodes.some(
    (node) => node.id === id || containsArea(node.children ?? [], id)
  );
}

/** Deepest area named by a path such as ``Kowloon · Yau Tsim Mong``. */
export function areaIdFromPath(tree: GeographicAreaNode[], path: string): string {
  const names = path
    .split('·')
    .map((part) => part.trim())
    .filter(Boolean);
  if (names.length === 0 || tree.length === 0) {
    return '';
  }
  const namedRoot = tree.find((node) => sameAreaName(node, names[0]));
  const rootChildren = tree.length === 1 ? (tree[0].children ?? []) : tree;
  let nodes = namedRoot ? (namedRoot.children ?? []) : rootChildren;
  const start = namedRoot ? 1 : 0;
  let deepest = namedRoot ? namedRoot.id : '';
  for (const name of names.slice(start)) {
    const next = nodes.find((node) => sameAreaName(node, name));
    if (!next) {
      break;
    }
    deepest = next.id;
    nodes = next.children ?? [];
  }
  return deepest;
}

/** Leaf when enrichment matched one, otherwise the region or district anchor. */
export function matchedAreaId(
  proposed: Record<string, unknown>,
  tree: GeographicAreaNode[],
  overrideAreaId?: string
): string {
  if (overrideAreaId) {
    return overrideAreaId;
  }
  const explicit = String(proposed.area_id ?? proposed.area_anchor_id ?? '');
  const fromPath = areaIdFromPath(
    tree,
    typeof proposed.area_path === 'string' ? proposed.area_path : ''
  );
  if (explicit && (tree.length === 0 || containsArea(tree, explicit))) {
    return explicit;
  }
  return fromPath || explicit;
}

function isBlankValue(item: unknown): boolean {
  if (typeof item === 'boolean') {
    return false;
  }
  if (item == null) {
    return true;
  }
  if (typeof item === 'string') {
    return item.trim() === '';
  }
  if (Array.isArray(item)) {
    return item.length === 0 || item.every((entry) => isBlankValue(entry));
  }
  if (typeof item === 'object') {
    const values = Object.values(item as Record<string, unknown>);
    return values.length === 0 || values.every((entry) => isBlankValue(entry));
  }
  return false;
}

function countedLabel(singular: string, plural: string, value: unknown): string | null {
  if (typeof value !== 'number') {
    return null;
  }
  return `${value} ${value === 1 ? singular : plural}`;
}

function currentFieldText(key: string, item: unknown): string | null {
  if (key === 'photos') {
    return countedLabel('photo', 'photos', item);
  }
  if (key === 'venues') {
    return countedLabel('venue', 'venues', item);
  }
  if (key === 'activities') {
    return countedLabel('activity', 'activities', item);
  }
  if (key === 'prices') {
    return countedLabel('price', 'prices', item);
  }
  if (key === 'schedules') {
    return countedLabel('schedule', 'schedules', item);
  }
  if (key === 'already_saved') {
    return item ? 'Already saved' : null;
  }
  if (key === 'changed_since_crawl') {
    return item ? 'Changed since crawl' : null;
  }
  if (key === 'logo' || key === 'logo_media_url') {
    return item ? 'Logo saved' : null;
  }
  return null;
}

function valueParts(
  value: Record<string, unknown>,
  format: (key: string, item: unknown) => string | null,
): string[] {
  return Object.entries(value)
    .filter(([key, item]) => key !== 'copyright_notice' && !isBlankValue(item))
    .map(([key, item]) => {
      const formatted = format(key, item);
      if (formatted) {
        return formatted;
      }
      if (item && typeof item === 'object') {
        return `${key}: ${JSON.stringify(item)}`;
      }
      return `${key}: ${String(item ?? '')}`;
    });
}

export function proposedText(value: Record<string, unknown> | null): string {
  if (!value) {
    return 'Empty';
  }
  const parts = valueParts(value, () => null);
  return parts.length === 0 ? 'Empty' : parts.join(' · ');
}

export function currentText(value: Record<string, unknown> | null): string {
  if (!value) {
    return 'Empty';
  }
  const parts = valueParts(value, currentFieldText);
  return parts.length === 0 ? 'Empty' : parts.join(' · ');
}

function mediaPreviewUrl(value: Record<string, unknown> | null): string | null {
  if (!value || typeof value.source_url !== 'string') {
    return null;
  }
  const raw = value.source_url.trim();
  if (!raw) {
    return null;
  }
  try {
    const url = new URL(raw);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      return null;
    }
    return raw;
  } catch {
    return null;
  }
}

function ProposalValue({ row }: { row: EnrichmentProposal }) {
  const preview = row.kind === 'add_media' ? mediaPreviewUrl(row.proposed_value) : null;
  if (!preview) {
    return <>{proposedText(row.proposed_value)}</>;
  }
  const alt =
    typeof row.proposed_value.alt === 'string' ? row.proposed_value.alt.trim() : '';
  const caption = alt && alt !== preview ? alt : '';
  const rest = { ...row.proposed_value };
  delete rest.source_url;
  delete rest.alt;
  delete rest.logo;
  delete rest.copyright_notice;
  const extra = proposedText(rest);
  return (
    <div className='space-y-2'>
      <MediaPreview src={preview} alt={caption || 'Proposed media'} />
      {caption ? <div>{caption}</div> : null}
      {extra !== 'Empty' ? <div>{extra}</div> : null}
    </div>
  );
}

function MediaPreview({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return <p className='text-xs text-ink-500'>Preview unavailable</p>;
  }
  return (
    <img
      src={src}
      alt={alt}
      data-testid='enrichment-media-preview'
      className='h-28 w-full max-w-xs rounded-md border border-brand-100 bg-brand-50 object-contain'
      loading='lazy'
      referrerPolicy='no-referrer'
      onError={() => setFailed(true)}
    />
  );
}

function statusTone(status: string) {
  if (status === 'ready' || status === 'applied') {
    return 'green' as const;
  }
  if (status === 'failed') {
    return 'red' as const;
  }
  if (status === 'running' || status === 'extracting') {
    return 'blue' as const;
  }
  return 'yellow' as const;
}

export function ProposalTable({
  rows,
  proposals,
  venues,
  activities,
  selected,
  overrides,
  applyErrors = {},
  onToggle,
  onOverride,
}: {
  rows: EnrichmentProposal[];
  proposals?: EnrichmentProposal[];
  venues: EnrichmentRead['venues'];
  activities?: EnrichmentRead['activities'];
  selected: string[];
  overrides: Record<string, EnrichmentOverride>;
  applyErrors?: Record<string, string>;
  onToggle: (id: string) => void;
  onOverride: (id: string, patch: EnrichmentOverride) => void;
}) {
  const areas = useGeographicAreas();
  const categories = useActivityCategories();
  const blockerContext = {
    proposals: proposals ?? rows,
    selected,
    venues,
    activities,
  };
  return (
    <AdminDataTable>
      <AdminDataTableHead>
        <tr>
          <AdminDataTableHeadCell className='w-10'>Select</AdminDataTableHeadCell>
          <AdminDataTableHeadCell>Proposal</AdminDataTableHeadCell>
          <AdminDataTableHeadCell priority='secondary'>Value</AdminDataTableHeadCell>
          <AdminDataTableHeadCell priority='tertiary'>Confidence</AdminDataTableHeadCell>
          <AdminDataTableHeadCell priority='secondary'>Status</AdminDataTableHeadCell>
        </tr>
      </AdminDataTableHead>
      <AdminDataTableBody>
        {rows.map((row) => {
          const current = currentText(row.current_value);
          const pending = row.status === 'pending';
          return (
            <tr key={row.id}>
              <AdminDataTableCell>
                <input
                  type='checkbox'
                  aria-label={`Select ${row.label}`}
                  checked={selected.includes(row.id)}
                  disabled={!pending}
                  onChange={() => onToggle(row.id)}
                />
              </AdminDataTableCell>
              <AdminDataTableCell>
                <AdminTableName>{row.label}</AdminTableName>
                <AdminDataTableCellMeta label='Now' until='secondary'>
                  {current}
                </AdminDataTableCellMeta>
                <AdminDataTableCellMeta label='Value' until='secondary'>
                  <ProposalValue row={row} />
                </AdminDataTableCellMeta>
              </AdminDataTableCell>
              <AdminDataTableCell priority='secondary'>
                <ProposalValue row={row} />
                <div className='mt-1 text-xs text-ink-500'>Now: {current}</div>
                {pending ? (
                  <ProposalFields
                    row={row}
                    venues={venues}
                    activities={activities}
                    blockerContext={blockerContext}
                    override={overrides[row.id] ?? {}}
                    applyError={applyErrors[row.id] ?? ''}
                    areaTree={areas.tree}
                    categoryTree={categories.tree}
                    onOverride={(patch) => onOverride(row.id, patch)}
                  />
                ) : null}
              </AdminDataTableCell>
              <AdminDataTableCell priority='tertiary'>
                <AdminTableNumber>
                  {formatAdminTablePercent(row.confidence)}
                  {row.unverified ? ' unverified' : ''}
                </AdminTableNumber>
              </AdminDataTableCell>
              <AdminDataTableCell priority='secondary'>
                <StatusBadge status={row.status} tone={statusTone(row.status)} />
              </AdminDataTableCell>
            </tr>
          );
        })}
      </AdminDataTableBody>
    </AdminDataTable>
  );
}

function ProposalFields({
  row,
  venues,
  activities,
  blockerContext,
  override,
  applyError,
  areaTree,
  categoryTree,
  onOverride,
}: {
  row: EnrichmentProposal;
  venues: EnrichmentRead['venues'];
  activities?: EnrichmentRead['activities'];
  blockerContext: {
    proposals: EnrichmentProposal[];
    selected: string[];
    venues?: EnrichmentRead['venues'];
    activities?: EnrichmentRead['activities'];
  };
  override: EnrichmentOverride;
  applyError: string;
  areaTree: ReturnType<typeof useGeographicAreas>['tree'];
  categoryTree: ReturnType<typeof useActivityCategories>['tree'];
  onOverride: (patch: EnrichmentOverride) => void;
}) {
  const proposed = row.proposed_value;
  if (row.kind === 'create_location') {
    const path = proposed.area_path ? String(proposed.area_path) : '';
    const said = proposed.area_name ? String(proposed.area_name) : '';
    const note = proposed.area_note ? String(proposed.area_note) : '';
    return (
      <div className='mt-3 max-w-xl'>
        {note ? <p className='mb-2 text-xs text-ink-500'>{note}</p> : null}
        <p className='mb-2 text-xs text-ink-500'>
          {path
            ? `Matched ${path}.`
            : said
              ? `Website said ${said}. Pick the neighbourhood if that does not match.`
              : 'Pick the neighbourhood for this address.'}
        </p>
        <CascadingAreaSelect
          tree={areaTree}
          value={matchedAreaId(proposed, areaTree, override.area_id)}
          onChange={(areaId) => onOverride({ ...override, area_id: areaId })}
        />
        <BlockerNotes
          row={row}
          override={override}
          applyError={applyError}
          context={blockerContext}
        />
      </div>
    );
  }
  if (row.kind === 'create_activity') {
    const ageMin = capShownAge(
      override.age_min ?? numberOrBlank(proposed.age_min)
    );
    const ageMax = capShownAge(
      override.age_max ?? numberOrBlank(proposed.age_max)
    );
    const words = proposed.category_words ? String(proposed.category_words) : '';
    const named = proposed.category_name ? String(proposed.category_name) : '';
    const said =
      words && named && words !== named ? `${words} (${named})` : words || named;
    return (
      <div className='mt-3 max-w-xl space-y-3'>
        {said ? (
          <p className='text-xs text-ink-500'>Website said {said}.</p>
        ) : null}
        <CascadingCategorySelect
          tree={categoryTree}
          value={override.category_id ?? String(proposed.category_id ?? '')}
          onChange={(categoryId) =>
            onOverride({ ...override, category_id: categoryId })
          }
        />
        <div className='grid gap-3 sm:grid-cols-2'>
          <div>
            <Label htmlFor={`age-min-${row.id}`}>Minimum age</Label>
            <Input
              id={`age-min-${row.id}`}
              type='number'
              min={0}
              max={MAX_LISTING_AGE}
              value={ageMin === undefined ? '' : String(ageMin)}
              onChange={(event) =>
                onOverride({
                  ...override,
                  age_min: event.target.value === '' ? undefined : Number(event.target.value),
                  age_max: ageMax,
                })
              }
            />
          </div>
          <div>
            <Label htmlFor={`age-max-${row.id}`}>Maximum age</Label>
            <Input
              id={`age-max-${row.id}`}
              type='number'
              min={0}
              max={MAX_LISTING_AGE}
              value={ageMax === undefined ? '' : String(ageMax)}
              onChange={(event) =>
                onOverride({
                  ...override,
                  age_min: ageMin,
                  age_max: event.target.value === '' ? undefined : Number(event.target.value),
                })
              }
            />
          </div>
        </div>
        <BlockerNotes
          row={row}
          override={override}
          applyError={applyError}
          context={blockerContext}
        />
      </div>
    );
  }
  if (row.kind === 'create_pricing' || row.kind === 'create_schedule') {
    return (
      <PricingFields
        row={row}
        venues={venues}
        activities={activities}
        blockerContext={blockerContext}
        override={override}
        applyError={applyError}
        onOverride={onOverride}
      />
    );
  }
  return (
    <BlockerNotes
      row={row}
      override={override}
      applyError={applyError}
      context={blockerContext}
    />
  );
}

function ActivityField({
  row,
  activities,
  override,
  onOverride,
}: {
  row: EnrichmentProposal;
  activities: NonNullable<EnrichmentRead['activities']>;
  override: EnrichmentOverride;
  onOverride: (patch: EnrichmentOverride) => void;
}) {
  return (
    <div>
      <Label htmlFor={`activity-${row.id}`}>Activity</Label>
      {activities.length === 0 ? (
        <p className='text-xs text-ink-500'>Add an activity before this row.</p>
      ) : (
        <Select
          id={`activity-${row.id}`}
          name='activity_id'
          value={override.activity_id ?? ''}
          onChange={(event) =>
            onOverride({
              ...override,
              activity_id: event.target.value || undefined,
            })
          }
        >
          <option value=''>Match the name</option>
          {activities.map((activity) => (
            <option key={activity.id} value={activity.id}>
              {activity.name}
            </option>
          ))}
        </Select>
      )}
    </div>
  );
}

function VenueField({
  row,
  venues,
  override,
  onOverride,
}: {
  row: EnrichmentProposal;
  venues: EnrichmentRead['venues'];
  override: EnrichmentOverride;
  onOverride: (patch: EnrichmentOverride) => void;
}) {
  return (
    <div>
      <Label htmlFor={`venue-${row.id}`}>Venue</Label>
      {venues.length === 0 ? (
        <p className='text-xs text-ink-500'>Add a location before this row.</p>
      ) : (
        <Select
          id={`venue-${row.id}`}
          name='location_id'
          value={override.location_id ?? ''}
          onChange={(event) =>
            onOverride({
              ...override,
              location_id: event.target.value || undefined,
            })
          }
        >
          <option value=''>Match the address</option>
          {venues.map((venue) => (
            <option key={venue.id} value={venue.id}>
              {locationListLabel(venue, venues, venue.address)}
            </option>
          ))}
        </Select>
      )}
    </div>
  );
}

function PricingFields({
  row,
  venues,
  activities,
  blockerContext,
  override,
  applyError,
  onOverride,
}: {
  row: EnrichmentProposal;
  venues: EnrichmentRead['venues'];
  activities?: EnrichmentRead['activities'];
  blockerContext: {
    proposals: EnrichmentProposal[];
    selected: string[];
    venues?: EnrichmentRead['venues'];
    activities?: EnrichmentRead['activities'];
  };
  override: EnrichmentOverride;
  applyError: string;
  onOverride: (patch: EnrichmentOverride) => void;
}) {
  const proposed = row.proposed_value;
  const pricing = row.kind === 'create_pricing';
  const pricingType = override.pricing_type ?? String(proposed.pricing_type || 'per_class');
  const amount = override.amount ?? String(proposed.amount ?? '');
  const currency = override.currency ?? String(proposed.currency || 'HKD');
  const sessions =
    typeof override.sessions_count === 'string'
      ? override.sessions_count
      : override.sessions_count !== undefined
        ? String(override.sessions_count)
        : proposedSessions(proposed.sessions_count);
  const knownCurrency = adminCurrencyOptions.some((option) => option.code === currency);
  const sessionsErrorId = `pricing-sessions-${row.id}`;
  const notes = visibleBlockers(row, override, blockerContext);
  const sessionsNote = notes.find((item) => item.field === 'sessions_count');
  const showActivity =
    Boolean(override.activity_id) || notes.some((item) => item.field === 'activity_name');
  const showVenue =
    Boolean(override.location_id) ||
    notes.some((item) => item.field === 'location_id') ||
    venues.length !== 1;
  return (
    <fieldset className='mt-3 max-w-xl space-y-3'>
      <legend className='sr-only'>{pricing ? 'Price' : 'Schedule'}</legend>
      {showActivity && activities ? (
        <ActivityField
          row={row}
          activities={activities}
          override={override}
          onOverride={onOverride}
        />
      ) : null}
      {showVenue ? (
        <VenueField row={row} venues={venues} override={override} onOverride={onOverride} />
      ) : null}
      {pricing ? (
        <>
      <div>
        <Label htmlFor={`pricing-type-${row.id}`}>Pricing type</Label>
        <Select
          id={`pricing-type-${row.id}`}
          name='pricing_type'
          value={pricingType}
          onChange={(event) =>
            onOverride({ ...override, pricing_type: event.target.value })
          }
        >
          {pricingOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>
      <div className='grid gap-3 sm:grid-cols-2'>
        <div>
          <Label htmlFor={`pricing-amount-${row.id}`}>Amount</Label>
          <Input
            id={`pricing-amount-${row.id}`}
            name='amount'
            inputMode='decimal'
            autoComplete='off'
            spellCheck={false}
            value={amount}
            onChange={(event) => onOverride({ ...override, amount: event.target.value })}
          />
        </div>
        <div>
          <Label htmlFor={`pricing-currency-${row.id}`}>Currency</Label>
          <Select
            id={`pricing-currency-${row.id}`}
            name='currency'
            value={currency}
            onChange={(event) =>
              onOverride({ ...override, currency: event.target.value })
            }
          >
            {knownCurrency ? null : <option value={currency}>{currency}</option>}
            {adminCurrencyOptions.map((option) => (
              <option key={option.code} value={option.code}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
      </div>
      {pricingType === 'per_sessions' ? (
        <div>
          <Label htmlFor={`pricing-sessions-${row.id}`}>Classes in the term</Label>
          <Input
            id={`pricing-sessions-${row.id}`}
            name='sessions_count'
            inputMode='numeric'
            autoComplete='off'
            spellCheck={false}
            aria-required='true'
            aria-describedby={sessionsNote ? sessionsErrorId : undefined}
            value={sessions}
            onChange={(event) =>
              onOverride({ ...override, sessions_count: event.target.value })
            }
          />
        </div>
      ) : null}
        </>
      ) : null}
      <BlockerNotes
        row={row}
        override={override}
        applyError={applyError}
        context={blockerContext}
        sessionsErrorId={sessionsNote ? sessionsErrorId : undefined}
      />
    </fieldset>
  );
}

function BlockerNotes({
  row,
  override,
  applyError,
  context,
  sessionsErrorId,
}: {
  row: EnrichmentProposal;
  override: EnrichmentOverride;
  applyError: string;
  context: {
    proposals: EnrichmentProposal[];
    selected: string[];
    venues?: EnrichmentRead['venues'];
    activities?: EnrichmentRead['activities'];
  };
  sessionsErrorId?: string;
}) {
  const notes = visibleBlockers(row, override, context);
  const extra =
    applyError && !notes.some((item) => item.message === applyError) ? applyError : '';
  if (notes.length === 0 && !extra) {
    return null;
  }
  return (
    <div className='mt-3 space-y-1'>
      {extra ? <AdminInlineError size='xs'>{extra}</AdminInlineError> : null}
      {notes.map((item) => (
        <BlockerLine key={item.field} item={item} sessionsErrorId={sessionsErrorId} />
      ))}
    </div>
  );
}

function BlockerLine({
  item,
  sessionsErrorId,
}: {
  item: EnrichmentBlocker;
  sessionsErrorId?: string;
}) {
  return (
    <AdminInlineError
      id={item.field === 'sessions_count' ? sessionsErrorId : undefined}
      size='xs'
    >
      {item.message}
    </AdminInlineError>
  );
}

function isLogoProposal(row: EnrichmentProposal | undefined): boolean {
  return Boolean(row && row.kind === 'add_media' && row.proposed_value.logo);
}

export function selectionAfterToggle(
  selected: string[],
  id: string,
  rows: EnrichmentProposal[]
): string[] {
  if (selected.includes(id)) {
    return selected.filter((item) => item !== id);
  }
  const row = rows.find((item) => item.id === id);
  if (!isLogoProposal(row)) {
    return [...selected, id];
  }
  const otherLogos = new Set(
    rows.filter((item) => isLogoProposal(item) && item.id !== id).map((item) => item.id)
  );
  return [...selected.filter((item) => !otherLogos.has(item)), id];
}

function proposedSessions(value: unknown): string {
  const count = positiveSessions(value);
  return count === undefined ? '' : String(count);
}

function numberOrBlank(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return undefined;
}

function capShownAge(value: number | undefined): number | undefined {
  if (value === undefined) {
    return undefined;
  }
  return Math.min(value, MAX_LISTING_AGE);
}
