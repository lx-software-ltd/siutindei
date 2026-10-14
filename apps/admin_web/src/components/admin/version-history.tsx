'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';

import { refreshCatalogHistory, getAdminQueryClient } from '../../lib/admin-query-client';
import { adminQueryKeys } from '../../lib/admin-query-keys';
import {
  forgetCatalogVersion,
  listCatalogVersions,
  listEntireCatalogHistory,
  type CatalogVersionRow,
} from '../../lib/api-client-versions';
import type { ApiMode } from '../../lib/resource-api';
import { AdminField, AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminReadOnlyValue } from '../ui/admin-read-only-value';
import { Button } from '../ui/button';
import { Select } from '../ui/select';

export type CatalogEntityType =
  | 'organization'
  | 'media'
  | 'location'
  | 'activity'
  | 'pricing'
  | 'schedule';

const REMOVABLE = new Set(['location', 'activity', 'pricing', 'schedule']);

export function catalogLatestVersion(
  currentVersion?: number | null,
  historyItems: Array<{ version: number }> = []
): number {
  const current = currentVersion && currentVersion > 0 ? currentVersion : 1;
  const fromHistory = historyItems.reduce(
    (latest, item) => (item.version > latest ? item.version : latest),
    1
  );
  return Math.max(current, fromHistory);
}

export function catalogVersionOptions(
  latestVersion: number,
  { allVersions }: { allVersions: boolean }
): number[] {
  const latest = latestVersion > 0 ? latestVersion : 1;
  if (!allVersions) {
    return [latest];
  }
  return Array.from({ length: latest }, (_, index) => index + 1);
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
        {`Read-only. Version ${row.version} is kept as it was. Editing the form writes a new version.`}
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
 * Version select for one catalog row. Admins can open an earlier version as
 * read-only details. Managers see the current version only.
 */
export function VersionHistory({
  mode,
  entityType,
  entityId,
  version,
  children,
  onHistoricalChange,
}: {
  mode: ApiMode;
  entityType: CatalogEntityType;
  entityId: string | null;
  version?: number | null;
  children?: ReactNode;
  onHistoricalChange?: (isHistorical: boolean) => void;
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
  const latestVersion = catalogLatestVersion(version, isAdmin ? items : []);
  const options = catalogVersionOptions(latestVersion, { allVersions: isAdmin });
  const [selectedVersion, setSelectedVersion] = useState(latestVersion);
  const [forgettingId, setForgettingId] = useState<string | null>(null);
  const [forgetError, setForgetError] = useState('');

  useEffect(() => {
    setSelectedVersion(latestVersion);
  }, [entityId, latestVersion]);

  const selected = items.find((row) => row.version === selectedVersion) ?? null;
  const isHistorical = Boolean(entityId) && selectedVersion < latestVersion;
  const removedItems = (removed.data?.items ?? []).filter((row) =>
    REMOVABLE.has(row.entity_type)
  );

  useEffect(() => {
    onHistoricalChange?.(isHistorical);
    return () => onHistoricalChange?.(false);
  }, [isHistorical, onHistoricalChange]);

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

  if (!entityId) {
    return children ?? null;
  }

  const selectId = `catalog-version-${entityType}-${entityId}`;
  const details = isHistorical ? (
    query.isError ? (
      <p className='text-sm text-slate-600'>This version is unavailable.</p>
    ) : query.isLoading ? (
      <p className='text-sm text-slate-600'>Loading version…</p>
    ) : selected ? (
      <VersionSnapshot row={selected} />
    ) : (
      <p className='text-sm text-slate-600'>This version is unavailable.</p>
    )
  ) : (
    children
  );

  return (
    <div className='space-y-4'>
      {details}
      <AdminField label='Version' htmlFor={selectId}>
        <Select
          id={selectId}
          value={String(selectedVersion)}
          onChange={(event) => setSelectedVersion(Number(event.target.value))}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
      </AdminField>
      {query.isError && !isHistorical ? (
        <p className='text-sm text-slate-600'>Versions are unavailable.</p>
      ) : null}
      {entityType === 'organization' && removedItems.length > 0 ? (
        <div className='space-y-2'>
          <p className='text-sm font-medium text-slate-900'>Removed records</p>
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
    </div>
  );
}
