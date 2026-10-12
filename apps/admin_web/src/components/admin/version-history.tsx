'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { getAdminQueryClient } from '../../lib/admin-query-client';
import { adminQueryKeys } from '../../lib/admin-query-keys';
import {
  listCatalogVersions,
  type CatalogVersionRow,
} from '../../lib/api-client-versions';
import type { ApiMode } from '../../lib/resource-api';
import { AdminDisclosure } from '../ui/admin-disclosure';
import { AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminReadOnlyValue } from '../ui/admin-read-only-value';

export type CatalogEntityType =
  | 'organization'
  | 'media'
  | 'location'
  | 'activity'
  | 'pricing'
  | 'schedule';

function sourceLabel(row: CatalogVersionRow) {
  if (row.reason === 'merged') {
    return 'Merge';
  }
  if (row.reason === 'forgotten') {
    return 'Forgotten';
  }
  if (row.reason === 'children') {
    return 'Child change';
  }
  if (row.import_job_id) {
    return 'Import';
  }
  if (row.user_id) {
    return row.user_id;
  }
  return 'System';
}

function changedSummary(row: CatalogVersionRow) {
  const fields = row.changed_fields ?? [];
  if (fields.length === 0) {
    return row.action;
  }
  return fields.slice(0, 6).join(', ');
}

function fieldLabel(key: string) {
  return key
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function formatSnapshotValue(value: unknown): string {
  if (value == null || value === '') {
    return '—';
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return '—';
    }
    return value
      .map((item) =>
        item != null && typeof item === 'object'
          ? JSON.stringify(item)
          : String(item)
      )
      .join(', ');
  }
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${fieldLabel(key)}: ${formatSnapshotValue(item)}`)
      .join('; ');
  }
  return String(value);
}

function VersionSnapshot({ row }: { row: CatalogVersionRow }) {
  const entries = Object.entries(row.snapshot).sort(([left], [right]) =>
    left.localeCompare(right)
  );
  return (
    <div className='rounded border border-slate-200 bg-white p-3'>
      <p className='text-sm text-slate-600'>
        Read-only. Version {row.version} is kept as it was. Editing the form
        writes a new version.
      </p>
      {entries.length === 0 ? (
        <p className='mt-3 text-sm text-slate-600'>No stored fields.</p>
      ) : (
        <AdminFieldGrid columns={2} className='mt-3'>
          {entries.map(([key, value]) => (
            <AdminReadOnlyValue
              key={key}
              label={fieldLabel(key)}
              span={typeof value === 'object' && value != null ? 'full' : 1}
            >
              {formatSnapshotValue(value)}
            </AdminReadOnlyValue>
          ))}
        </AdminFieldGrid>
      )}
    </div>
  );
}

/**
 * Read-only version and, for admins, the history of one catalog row.
 * Managers see the version only.
 */
export function VersionHistory({
  mode,
  entityType,
  entityId,
  version,
}: {
  mode: ApiMode;
  entityType: CatalogEntityType;
  entityId: string | null;
  version?: number | null;
}) {
  const isAdmin = mode === 'admin';
  const query = useQuery(
    {
      queryKey: [...adminQueryKeys.catalogVersions(), entityType, entityId],
      enabled: isAdmin && Boolean(entityId),
      queryFn: () =>
        listCatalogVersions({
          entity_type: entityType,
          entity_id: entityId ?? undefined,
        }),
    },
    getAdminQueryClient()
  );
  const items = query.data?.items ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = items.find((row) => row.id === selectedId) ?? null;

  return (
    <div className='mt-4 space-y-3'>
      <AdminReadOnlyValue label='Version'>
        {version ? `v${version}` : '—'}
      </AdminReadOnlyValue>
      {isAdmin && entityId ? (
        <AdminDisclosure
          id={`version-history-${entityType}-${entityId}`}
          title='History'
          summary={query.isLoading ? 'Loading' : `${items.length}`}
        >
          {query.isError ? (
            <p className='text-sm text-slate-600'>History is unavailable.</p>
          ) : null}
          {items.length === 0 && !query.isLoading ? (
            <p className='text-sm text-slate-600'>No versions yet.</p>
          ) : (
            <>
              <ul className='space-y-2 text-sm text-slate-700'>
                {items.map((row) => (
                  <li key={row.id}>
                    <button
                      type='button'
                      aria-pressed={row.id === selectedId}
                      aria-label={`View version ${row.version}`}
                      onClick={() =>
                        setSelectedId((current) =>
                          current === row.id ? null : row.id
                        )
                      }
                      className='w-full rounded border border-slate-200 bg-white p-2 text-left hover:bg-slate-50'
                    >
                      <span className='font-medium'>v{row.version}</span>
                      {' · '}
                      {row.action}
                      {' · '}
                      {sourceLabel(row)}
                      {' · '}
                      {new Date(row.created_at).toLocaleString()}
                      <span className='block text-slate-500'>
                        {changedSummary(row)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              {selected ? <VersionSnapshot row={selected} /> : null}
            </>
          )}
        </AdminDisclosure>
      ) : null}
    </div>
  );
}
