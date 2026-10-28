'use client';

import { useState } from 'react';

import { useActivityCategories } from '../../hooks/use-activity-categories';
import { useGeographicAreas } from '../../hooks/use-geographic-areas';
import type {
  EnrichmentOverride,
  EnrichmentProposal,
} from '../../lib/api-client-enrichment';
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
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select } from '../ui/select';
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

export function proposedText(value: Record<string, unknown> | null): string {
  if (!value) {
    return 'Empty';
  }
  return Object.entries(value)
    .filter(([key]) => key !== 'copyright_notice')
    .map(([key, item]) => {
      if (item && typeof item === 'object') {
        return `${key}: ${JSON.stringify(item)}`;
      }
      return `${key}: ${String(item ?? '')}`;
    })
    .join(' · ');
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
      {extra ? <div>{extra}</div> : null}
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
  venues,
  selected,
  overrides,
  onToggle,
  onOverride,
}: {
  rows: EnrichmentProposal[];
  venues: Array<{ id: string; address: string }>;
  selected: string[];
  overrides: Record<string, EnrichmentOverride>;
  onToggle: (id: string) => void;
  onOverride: (id: string, patch: EnrichmentOverride) => void;
}) {
  const areas = useGeographicAreas();
  const categories = useActivityCategories();
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
          const current = proposedText(row.current_value);
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
                    override={overrides[row.id] ?? {}}
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
  override,
  areaTree,
  categoryTree,
  onOverride,
}: {
  row: EnrichmentProposal;
  venues: Array<{ id: string; address: string }>;
  override: EnrichmentOverride;
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
      </div>
    );
  }
  if (row.kind === 'create_activity') {
    const ageMin = override.age_min ?? numberOrBlank(proposed.age_min);
    const ageMax = override.age_max ?? numberOrBlank(proposed.age_max);
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
              max={120}
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
              max={120}
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
      </div>
    );
  }
  if (
    (row.kind === 'create_pricing' || row.kind === 'create_schedule') &&
    venues.length !== 1
  ) {
    return (
      <div className='mt-3 max-w-sm'>
        <Label htmlFor={`venue-${row.id}`}>Venue</Label>
        {venues.length === 0 ? (
          <p className='text-xs text-ink-500'>Add a location before this row.</p>
        ) : (
          <Select
            id={`venue-${row.id}`}
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
                {venue.address}
              </option>
            ))}
          </Select>
        )}
      </div>
    );
  }
  return null;
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

function numberOrBlank(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return undefined;
}
