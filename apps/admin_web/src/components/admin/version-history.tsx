'use client';

import {
  createContext,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useQuery } from '@tanstack/react-query';

import { clsx } from 'clsx';

import { refreshCatalogHistory, getAdminQueryClient } from '../../lib/admin-query-client';
import { adminQueryKeys } from '../../lib/admin-query-keys';
import { listCognitoUsers } from '../../lib/api-client-cognito';
import {
  forgetCatalogVersion,
  listCatalogVersions,
  listEntireCatalogHistory,
  type CatalogVersionRow,
} from '../../lib/api-client-versions';
import type { ApiMode } from '../../lib/resource-api';
import { AdminField, type AdminFieldProps } from '../ui/admin-field-grid';
import { Button } from '../ui/button';
import { snapshotFieldText } from './catalog-version-snapshot';

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

function stableValue(value: unknown): string {
  if (value == null || value === '') {
    return 'null';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return JSON.stringify(value);
}

function valuesDiffer(left: unknown, right: unknown): boolean {
  return stableValue(left) !== stableValue(right);
}

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
  return fields.slice(0, 4).join(', ');
}

function formatVersionDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function fieldLabel(key: string) {
  return key
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function recordName(row: CatalogVersionRow) {
  const name = row.snapshot.name ?? row.snapshot.address;
  return typeof name === 'string' && name.trim() ? name : row.entity_type;
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

export interface CatalogVersionView {
  entityId: string | null;
  isAdmin: boolean;
  isLoading: boolean;
  isHistorical: boolean;
  locked: boolean;
  latestVersion: number;
  selectedVersion: number;
  items: CatalogVersionRow[];
  snapshot: Record<string, unknown> | null;
  latestSnapshot: Record<string, unknown> | null;
  selectVersion: (version: number) => void;
  backToLatest: () => void;
  changed: (key: string) => boolean;
  latestLabel: (key: string) => string;
}

export function useCatalogVersion({
  mode,
  entityType,
  entityId,
  version,
}: {
  mode: ApiMode;
  entityType: CatalogEntityType;
  entityId: string | null;
  version?: number | null;
}): CatalogVersionView {
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
  const items = query.data?.items ?? [];
  const latestVersion = catalogLatestVersion(version, isAdmin ? items : []);
  const [selection, setSelection] = useState<{
    entityId: string | null;
    latest: number;
    selected: number;
  } | null>(null);
  const selectedVersion =
    selection && selection.entityId === entityId && selection.latest === latestVersion
      ? selection.selected
      : latestVersion;

  const selected = items.find((row) => row.version === selectedVersion) ?? null;
  const latestRow =
    items.find((row) => row.version === latestVersion) ??
    items.reduce<CatalogVersionRow | null>(
      (best, row) => (!best || row.version > best.version ? row : best),
      null
    );
  const snapshot = selected?.snapshot ?? null;
  const latestSnapshot = latestRow?.snapshot ?? null;
  const isHistorical = Boolean(entityId) && selectedVersion < latestVersion;
  const locked = isHistorical && snapshot != null;

  function changed(key: string) {
    if (!locked || !snapshot || !latestSnapshot) {
      return false;
    }
    if (!(key in snapshot) && !(key in latestSnapshot)) {
      return false;
    }
    return valuesDiffer(snapshot[key], latestSnapshot[key]);
  }

  return {
    entityId,
    isAdmin,
    isLoading: query.isLoading,
    isHistorical,
    locked,
    latestVersion,
    selectedVersion,
    items: [...items].sort((left, right) => right.version - left.version),
    snapshot: locked ? snapshot : null,
    latestSnapshot,
    selectVersion: (next: number) =>
      setSelection({ entityId, latest: latestVersion, selected: next }),
    backToLatest: () =>
      setSelection({ entityId, latest: latestVersion, selected: latestVersion }),
    changed,
    latestLabel: (key: string) => snapshotFieldText(key, latestSnapshot?.[key]),
  };
}

const CatalogVersionContext = createContext<CatalogVersionView | null>(null);

export function VersionFields({
  view,
  children,
}: {
  view: CatalogVersionView;
  children: ReactNode;
}) {
  return (
    <CatalogVersionContext.Provider value={view}>{children}</CatalogVersionContext.Provider>
  );
}

export function VersionField({
  versionKey,
  hint,
  className,
  children,
  ...rest
}: AdminFieldProps & { versionKey?: string | string[] }) {
  const view = useContext(CatalogVersionContext);
  const keys = versionKey == null ? [] : Array.isArray(versionKey) ? versionKey : [versionKey];
  const changed = Boolean(view?.locked && keys.some((key) => view.changed(key)));
  const latest = changed && view ? view.latestLabel(keys[0] ?? '') : null;
  return (
    <AdminField
      {...rest}
      className={clsx(
        className,
        changed && 'rounded-md bg-amber-50 p-2 ring-1 ring-amber-200'
      )}
      hint={
        changed ? (
          <>
            <span className='text-amber-800'>Latest: {latest}</span>
            {hint ? <span className='mt-1 block'>{hint}</span> : null}
          </>
        ) : (
          hint
        )
      }
    >
      {children}
    </AdminField>
  );
}

export function VersionViewBanner({ view }: { view: CatalogVersionView }) {
  if (!view.isHistorical) {
    return null;
  }
  return (
    <div className='flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950'>
      <p>
        {view.snapshot
          ? `Viewing version ${view.selectedVersion} of ${view.latestVersion} · read-only`
          : view.isLoading
            ? 'Loading version…'
            : 'This version is unavailable.'}
      </p>
      <Button type='button' size='sm' variant='secondary' onClick={view.backToLatest}>
        Back to latest
      </Button>
    </div>
  );
}

export function HistoricalRowMark({
  active,
  version,
}: {
  active: boolean;
  version: number;
}) {
  if (!active) {
    return null;
  }
  return (
    <span className='ml-2 inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900'>
      v{version}
    </span>
  );
}

export function VersionSwitcher({ view }: { view: CatalogVersionView }) {
  const menuId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [menuStyle, setMenuStyle] = useState<{ top: number; left: number; flip: boolean }>({
    top: 0,
    left: 0,
    flip: false,
  });
  const needsEmails = view.items.some((row) => row.user_id && !row.import_job_id);
  const emails = useQuery(
    {
      queryKey: [...adminQueryKeys.catalogVersions(), 'actors'],
      enabled: view.isAdmin && needsEmails && open,
      staleTime: 60_000,
      queryFn: loadEmailById,
    },
    getAdminQueryClient()
  );
  const emailById = emails.data ?? {};
  const isLatest = view.selectedVersion === view.latestVersion;
  const label = isLatest
    ? `Version ${view.selectedVersion} · Latest`
    : `Version ${view.selectedVersion}`;

  useEffect(() => {
    if (!open) {
      return;
    }
    function place() {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) {
        return;
      }
      const flip = rect.bottom + 280 > window.innerHeight;
      setMenuStyle({ top: flip ? rect.top - 4 : rect.bottom + 4, left: rect.left, flip });
    }
    function onPointer(event: MouseEvent) {
      const target = event.target as Node;
      if (buttonRef.current?.contains(target) || menuRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    }
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!view.entityId) {
    return null;
  }
  if (!view.isAdmin) {
    return (
      <span className='inline-flex h-8 items-center rounded-full bg-slate-100 px-2.5 text-xs font-medium text-slate-700'>
        {`Version ${view.latestVersion}`}
      </span>
    );
  }

  const rows =
    view.items.length > 0
      ? view.items
      : [
          {
            id: 'current',
            entity_type: '',
            entity_id: view.entityId,
            version: view.latestVersion,
            action: 'current',
            snapshot: {},
            created_at: '',
          } satisfies CatalogVersionRow,
        ];

  return (
    <div className='relative'>
      <button
        ref={buttonRef}
        type='button'
        aria-haspopup='menu'
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => {
          if (!open) {
            const rect = buttonRef.current?.getBoundingClientRect();
            if (rect) {
              const flip = rect.bottom + 280 > window.innerHeight;
              setMenuStyle({
                top: flip ? rect.top - 4 : rect.bottom + 4,
                left: rect.left,
                flip,
              });
            }
          }
          setOpen((current) => !current);
        }}
        className={clsx(
          'inline-flex h-8 items-center gap-1 rounded-full border px-2.5 text-xs font-medium',
          view.isHistorical
            ? 'border-amber-300 bg-amber-50 text-amber-950'
            : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
        )}
      >
        {label}
        <span aria-hidden='true'>▾</span>
      </button>
      {open ? (
        <div
          ref={menuRef}
          id={menuId}
          role='menu'
          style={{
            position: 'fixed',
            top: menuStyle.top,
            left: menuStyle.left,
            transform: menuStyle.flip ? 'translateY(-100%)' : undefined,
          }}
          className='z-50 w-72 max-w-[calc(100vw-2rem)] overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg'
        >
          {view.isLoading ? (
            <p className='px-3 py-2 text-sm text-slate-600'>Loading versions…</p>
          ) : (
            <ul className='max-h-72 overflow-auto py-1'>
              {rows.map((row) => {
                const selected = row.version === view.selectedVersion;
                const latest = row.version === view.latestVersion;
                return (
                  <li key={row.id}>
                    <button
                      type='button'
                      role='menuitem'
                      onClick={() => {
                        view.selectVersion(row.version);
                        setOpen(false);
                      }}
                      className={clsx(
                        'flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm hover:bg-slate-50',
                        selected && 'bg-slate-50'
                      )}
                    >
                      <span className='font-medium text-slate-900'>
                        {`Version ${row.version}`}
                        {latest ? ' · Latest' : ''}
                      </span>
                      {row.created_at ? (
                        <span className='text-xs text-slate-500'>
                          {formatVersionDate(row.created_at)}
                          {' · '}
                          {sourceLabel(row, emailById)}
                          {' · '}
                          {changedSummary(row)}
                        </span>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function RemovedCatalogRecords({ orgId }: { orgId: string }) {
  const removed = useQuery(
    {
      queryKey: [...adminQueryKeys.catalogVersions(), 'removed', orgId],
      enabled: Boolean(orgId),
      staleTime: 0,
      queryFn: () =>
        listCatalogVersions({
          org_id: orgId,
          blocking: true,
        }),
    },
    getAdminQueryClient()
  );
  const [forgettingId, setForgettingId] = useState<string | null>(null);
  const [forgetError, setForgetError] = useState('');
  const removedItems = (removed.data?.items ?? []).filter((row) =>
    REMOVABLE.has(row.entity_type)
  );
  if (removed.isError || removedItems.length === 0) {
    return null;
  }

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
    <div className='col-span-full space-y-2 border-t border-slate-200 pt-4'>
      <p className='text-sm font-medium text-slate-900'>Removed records</p>
      <p className='text-sm text-slate-600'>
        Forgetting one lets the next import create it again.
      </p>
      {forgetError ? <p className='text-sm text-red-700'>{forgetError}</p> : null}
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
  );
}
