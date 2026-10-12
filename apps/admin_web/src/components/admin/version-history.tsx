'use client';

import { useQuery } from '@tanstack/react-query';

import { getAdminQueryClient } from '../../lib/admin-query-client';
import { adminQueryKeys } from '../../lib/admin-query-keys';
import {
  listCatalogVersions,
  type CatalogVersionRow,
} from '../../lib/api-client-versions';
import type { ApiMode } from '../../lib/resource-api';
import { AdminDisclosure } from '../ui/admin-disclosure';
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
            <ul className='space-y-2 text-sm text-slate-700'>
              {items.map((row) => (
                <li key={row.id} className='rounded border border-slate-200 p-2'>
                  <span className='font-medium'>v{row.version}</span>
                  {' · '}
                  {row.action}
                  {' · '}
                  {sourceLabel(row)}
                  {' · '}
                  {new Date(row.created_at).toLocaleString()}
                  <span className='block text-slate-500'>{changedSummary(row)}</span>
                </li>
              ))}
            </ul>
          )}
        </AdminDisclosure>
      ) : null}
    </div>
  );
}
