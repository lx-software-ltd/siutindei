'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { refreshCatalogHistory, getAdminQueryClient } from '../../lib/admin-query-client';
import { adminQueryKeys } from '../../lib/admin-query-keys';
import { listCognitoUsers } from '../../lib/api-client-cognito';
import {
  forgetCatalogVersion,
  listCatalogVersions,
  listEntireCatalogHistory,
  type CatalogVersionRow,
} from '../../lib/api-client-versions';
import { formatDateTime } from '../../lib/date-utils';
import type { ApiMode } from '../../lib/resource-api';
import { AdminDisclosure } from '../ui/admin-disclosure';
import { AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminReadOnlyValue } from '../ui/admin-read-only-value';
import { Button } from '../ui/button';

export type CatalogEntityType =
  | 'organization'
  | 'media'
  | 'location'
  | 'activity'
  | 'pricing'
  | 'schedule';

const REMOVABLE = new Set(['location', 'activity', 'pricing', 'schedule']);

function sourceLabel(row: CatalogVersionRow, emailById: Record<string, string>) {
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
    return emailById[row.user_id] ?? 'Admin';
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

function recordName(row: CatalogVersionRow) {
  const name = row.snapshot.name ?? row.snapshot.address;
  return typeof name === 'string' && name.trim() ? name : row.entity_type;
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

async function loadEmailById() {
  const emailById: Record<string, string> = {};
  let paginationToken: string | undefined;
  do {
    const response = await listCognitoUsers(paginationToken, 60);
    for (const user of response.items) {
      if (user.email) {
        emailById[user.sub] = user.email;
      }
    }
    paginationToken = response.pagination_token ?? undefined;
  } while (paginationToken);
  return emailById;
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
      staleTime: 0,
      queryFn: () =>
        listEntireCatalogHistory({
          entity_type: entityType,
          entity_id: entityId ?? undefined,
        }),
    },
    getAdminQueryClient()
  );
  const removed = useQuery(
    {
      queryKey: [...adminQueryKeys.catalogVersions(), 'removed', entityId],
      enabled: isAdmin && entityType === 'organization' && Boolean(entityId),
      staleTime: 0,
      queryFn: () =>
        listCatalogVersions({
          org_id: entityId ?? undefined,
          blocking: true,
        }),
    },
    getAdminQueryClient()
  );
  const items = query.data?.items ?? [];
  const needsEmails = items.some((row) => row.user_id && !row.import_job_id);
  const emails = useQuery(
    {
      queryKey: [...adminQueryKeys.catalogVersions(), 'actors'],
      enabled: isAdmin && needsEmails,
      staleTime: 60_000,
      queryFn: loadEmailById,
    },
    getAdminQueryClient()
  );
  const emailById = emails.data ?? {};
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [forgettingId, setForgettingId] = useState<string | null>(null);
  const [forgetError, setForgetError] = useState('');
  const selected = items.find((row) => row.id === selectedId) ?? null;
  const removedItems = (removed.data?.items ?? []).filter((row) =>
    REMOVABLE.has(row.entity_type)
  );

  async function forget(row: CatalogVersionRow) {
    setForgettingId(row.id);
    setForgetError('');
    try {
      await forgetCatalogVersion(row.id);
      refreshCatalogHistory();
    } catch {
      setForgetError('Could not forget this removed record.');
    } finally {
      setForgettingId(null);
    }
  }

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
                      {sourceLabel(row, emailById)}
                      {' · '}
                      {formatDateTime(row.created_at)}
                      <span className='block text-slate-500'>
                        {changedSummary(row)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              {query.data?.next_cursor ? (
                <p className='text-sm text-slate-600'>
                  Older versions are still stored. Open the record again to
                  load the next page.
                </p>
              ) : null}
              {selected ? <VersionSnapshot row={selected} /> : null}
            </>
          )}
          {entityType === 'organization' && removedItems.length > 0 ? (
            <div className='mt-4 space-y-2'>
              <p className='text-sm font-medium text-slate-900'>
                Removed records
              </p>
              <p className='text-sm text-slate-600'>
                Forgetting one lets the next import create it again.
              </p>
              {forgetError ? (
                <p className='text-sm text-red-700'>{forgetError}</p>
              ) : null}
              <ul className='space-y-2 text-sm text-slate-700'>
                {removedItems.map((row) => (
                  <li
                    key={row.id}
                    className='flex items-center justify-between gap-3 rounded border border-slate-200 bg-white p-2'
                  >
                    <span>
                      {fieldLabel(row.entity_type)} · {recordName(row)}
                    </span>
                    <Button
                      type='button'
                      variant='danger'
                      size='sm'
                      loading={forgettingId === row.id}
                      onClick={() => void forget(row)}
                    >
                      Forget
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </AdminDisclosure>
      ) : null}
    </div>
  );
}
