'use client';

import { useActivityCategories } from '../../hooks/use-activity-categories';
import { useGeographicAreas } from '../../hooks/use-geographic-areas';
import type {
  EnrichmentOverride,
  EnrichmentProposal,
} from '../../lib/api-client-enrichment';
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
          const value = proposedText(row.proposed_value);
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
                  {value}
                </AdminDataTableCellMeta>
              </AdminDataTableCell>
              <AdminDataTableCell priority='secondary'>
                <div>{value}</div>
                <div className='mt-1 text-xs text-slate-500'>Now: {current}</div>
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
    return (
      <div className='mt-3 max-w-xl'>
        <p className='mb-2 text-xs text-slate-500'>
          {proposed.area_name
            ? `Website said ${String(proposed.area_name)}. Pick the neighbourhood if that does not match.`
            : 'Pick the neighbourhood for this address.'}
        </p>
        <CascadingAreaSelect
          tree={areaTree}
          value={override.area_id ?? ''}
          onChange={(areaId) => onOverride({ ...override, area_id: areaId })}
        />
      </div>
    );
  }
  if (row.kind === 'create_activity') {
    const ageMin = override.age_min ?? numberOrBlank(proposed.age_min);
    const ageMax = override.age_max ?? numberOrBlank(proposed.age_max);
    return (
      <div className='mt-3 max-w-xl space-y-3'>
        {proposed.category_name ? (
          <p className='text-xs text-slate-500'>
            Website said {String(proposed.category_name)}.
          </p>
        ) : null}
        <CascadingCategorySelect
          tree={categoryTree}
          value={override.category_id ?? ''}
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
          <p className='text-xs text-slate-500'>Add a location before this row.</p>
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

function numberOrBlank(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return undefined;
}
