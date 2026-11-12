'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';

import { AuditHighlightedJson } from '@/components/admin/audit-highlighted-json';
import { IdentityProviderBadge } from '@/components/admin/cognito-users/badges';
import { GearIcon, JobIcon, KeyIcon, PersonIcon } from '@/components/icons/action-icons';
import { StatusBanner } from '@/components/status-banner';
import { useExpandedRecord } from '@/hooks/use-expanded-record';
import { usePaginatedList } from '@/hooks/use-paginated-list';
import { type AuditLogsFilters } from '@/lib/api-client';
import { listApiKeys } from '@/lib/api-client-api-keys';
import { listAuditLogs } from '@/lib/api-client-audit';
import { listCognitoUsers } from '@/lib/api-client-cognito';
import { formatAdminPageName } from '@/lib/admin-page-name';
import { getAdminQueryClient } from '@/lib/admin-query-client';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import {
  formatAuditActor,
  type AuditActor,
  type AuditActorUser,
} from '@/lib/audit-actor';
import { AUDITABLE_TABLES } from '@/lib/audit-tables';
import { formatDateTime } from '@/lib/date-utils';
import type { AuditLog } from '@/types/admin';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '@/components/ui/admin-data-table';
import { AdminEditorPanel } from '@/components/ui/admin-editor-panel';
import { AdminFieldGrid } from '@/components/ui/admin-field-grid';
import {
  AdminFilterBar,
  AdminFilterField,
} from '@/components/ui/admin-filter-bar';
import { ResourceTableShell } from '@/components/ui/resource-table-shell';
import { AdminReadOnlyValue } from '@/components/ui/admin-read-only-value';
import { Select } from '@/components/ui/select';
import { StatusBadge } from '@/components/ui/status-badge';
import {
  adminTableText,
  AdminTableName,
  AdminTableTime,
} from '@/components/ui/admin-table-value';

const PAGE_NAME = formatAdminPageName('Audit logs');

type ActionFilter = 'all' | 'insert' | 'update' | 'delete';

interface AuditLogListFilters {
  action: ActionFilter;
  table: string;
  timeRange: string;
}

const defaultAuditLogFilters: AuditLogListFilters = {
  action: 'all',
  table: 'all',
  timeRange: '24h',
};

const TIME_RANGES = [
  { value: '', label: 'All time' },
  { value: '1h', label: 'Last hour' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
];

function getTimestamp(range: string): string | undefined {
  if (!range) {
    return undefined;
  }
  const now = new Date();
  switch (range) {
    case '1h':
      return new Date(now.getTime() - 60 * 60 * 1000).toISOString();
    case '24h':
      return new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();
    case '7d':
      return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
    case '30d':
      return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
    default:
      return undefined;
  }
}

function formatAuditAction(action: string): string {
  return action.toLowerCase();
}

function auditJsonRecord(
  value: AuditLog['old_values'] | AuditLog['new_values']
): Record<string, unknown> | null {
  if (!value || Object.keys(value).length === 0) {
    return null;
  }
  return value;
}

export async function loadApiKeyNames(): Promise<Record<string, string>> {
  const nameById: Record<string, string> = {};
  let cursor: string | undefined;
  const seen = new Set<string>();
  for (;;) {
    const response = await listApiKeys(cursor, 200);
    for (const key of response.items) {
      const name = key.name.trim();
      if (name) {
        nameById[key.id] = name;
      }
    }
    const next = response.next_cursor ?? undefined;
    if (!next || seen.has(next)) {
      return nameById;
    }
    seen.add(next);
    cursor = next;
  }
}

function ActorMark({ label, children }: { label?: string; children: ReactNode }) {
  if (!label) {
    return (
      <span className='inline-flex shrink-0 items-center text-ink-500'>{children}</span>
    );
  }
  return (
    <span
      role='img'
      title={label}
      aria-label={label}
      className='inline-flex shrink-0 items-center text-ink-500'
    >
      {children}
    </span>
  );
}

export function AuditActorValue({ actor }: { actor: AuditActor }) {
  const text = adminTableText(actor.text);
  let mark: ReactNode;
  if (actor.kind === 'system') {
    mark = (
      <ActorMark>
        <GearIcon className='h-4 w-4' />
      </ActorMark>
    );
  } else if (actor.kind === 'job') {
    mark = (
      <ActorMark>
        <JobIcon className='h-4 w-4' />
      </ActorMark>
    );
  } else if (actor.kind === 'key') {
    mark = (
      <ActorMark label='API key'>
        <KeyIcon className='h-4 w-4' />
      </ActorMark>
    );
  } else if (actor.username) {
    mark = <IdentityProviderBadge username={actor.username} />;
  } else {
    mark = (
      <ActorMark label='User'>
        <PersonIcon className='h-4 w-4' />
      </ActorMark>
    );
  }
  return (
    <span className='inline-flex min-w-0 items-center gap-1.5' data-actor-kind={actor.kind}>
      <span className='min-w-0 break-words'>{text}</span>
      {mark}
    </span>
  );
}

/** Phone caption. An unknown name keeps the column name and the actor icon. */
export function AuditActorCaption({ actor }: { actor: AuditActor }) {
  if (actor.text !== '—') {
    return <AuditActorValue actor={actor} />;
  }
  return (
    <span className='inline-flex min-w-0 items-center gap-1.5'>
      <span>Actor</span>
      <AuditActorValue actor={actor} />
    </span>
  );
}

function ActionBadge({ action }: { action: AuditLog['action'] }) {
  const normalized = action.toUpperCase();
  const tone = normalized === 'INSERT' ? 'green' : normalized === 'DELETE' ? 'red' : 'blue';

  return <StatusBadge status={action} tone={tone} label={formatAuditAction(action)} />;
}

export function AuditLogsPanel() {
  const expanded = useExpandedRecord({ paramName: 'audit-log' });
  const [usersById, setUsersById] = useState<Record<string, AuditActorUser>>({});
  const userLookupPromise = useRef<Promise<Record<string, AuditActorUser>> | null>(null);
  const userLookupRef = useRef<Record<string, AuditActorUser>>({});
  const isMountedRef = useRef(true);

  const loadCognitoUsers = useCallback(async () => {
    if (Object.keys(userLookupRef.current).length > 0) {
      if (isMountedRef.current) {
        setUsersById(userLookupRef.current);
      }
      return userLookupRef.current;
    }
    if (userLookupPromise.current) {
      return userLookupPromise.current;
    }

    userLookupPromise.current = (async () => {
      try {
        const directory: Record<string, AuditActorUser> = {};
        let paginationToken: string | undefined;

        do {
          const response = await listCognitoUsers(paginationToken, 60);
          for (const user of response.items) {
            const email = user.email?.trim();
            if (!email) {
              continue;
            }
            directory[user.sub] = {
              email,
              username: user.username,
            };
          }
          paginationToken = response.pagination_token ?? undefined;
        } while (paginationToken);

        userLookupRef.current = directory;
        if (isMountedRef.current) {
          setUsersById(directory);
        }
        return directory;
      } catch {
        return {};
      } finally {
        userLookupPromise.current = null;
      }
    })();

    return userLookupPromise.current;
  }, []);

  const list = usePaginatedList<AuditLog, AuditLogListFilters>({
    queryKey: adminQueryKeys.auditLogs(),
    defaultFilters: defaultAuditLogFilters,
    limit: 50,
    errorPrefix: 'Failed to load audit logs',
    fetcher: async ({ action, table, timeRange, cursor, limit }) => {
      const filters: AuditLogsFilters = {};
      if (action !== 'all') {
        filters.action = action.toUpperCase() as NonNullable<AuditLogsFilters['action']>;
      }
      if (table !== 'all') {
        filters.table = table;
      }
      const since = getTimestamp(timeRange);
      if (since) {
        filters.since = since;
      }
      const response = await listAuditLogs(filters, cursor ?? undefined, limit);
      return {
        items: response.items,
        nextCursor: response.next_cursor ?? null,
      };
    },
  });

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    void loadCognitoUsers();
  }, [loadCognitoUsers]);

  const keyNames = useQuery(
    {
      queryKey: adminQueryKeys.apiKeyActorNames(),
      queryFn: loadApiKeyNames,
    },
    getAdminQueryClient()
  );

  const getActor = useCallback(
    (userId: string | null | undefined) =>
      formatAuditActor(userId, usersById, keyNames.data ?? {}),
    [keyNames.data, usersById]
  );

  const selected = list.items.find((item) => item.id === expanded.expandedId) ?? null;

  const detail = selected ? (
    <AuditLogDetail log={selected} actor={getActor(selected.user_id)} />
  ) : null;

  return (
    <div className='space-y-4'>
    <h2 className='sr-only'>{PAGE_NAME}</h2>
    {keyNames.isError ? (
      <StatusBanner kind='error'>Could not load API key names.</StatusBanner>
    ) : null}
    <ResourceTableShell
      ariaLabel={PAGE_NAME}
      rows={list.items}
      getLabel={(item) => `${item.table_name} ${formatAuditAction(item.action)}`}
      middleColumnCount={4}
      hasActions={false}
      isLoading={list.isLoading}
      isLoadingMore={list.isLoadingMore}
      hasMore={list.hasMore}
      onLoadMore={list.loadMore}
      error={list.error}
      emptyLabel='No audit logs found matching your filters.'
      isExpanded={expanded.isExpanded}
      onToggle={expanded.toggle}
      detail={detail}
      filters={
        <AdminFilterBar>
          <AdminFilterField>
            <Select
              id='table-filter'
              aria-label='Table'
              value={list.filters.table}
              onChange={(event) => {
                list.setFilter('table', event.target.value);
              }}
            >
              <option value='all'>All tables</option>
              {AUDITABLE_TABLES.map((table) => (
                <option key={table} value={table}>
                  {table}
                </option>
              ))}
            </Select>
          </AdminFilterField>
          <AdminFilterField>
            <Select
              id='action-filter'
              aria-label='Action'
              value={list.filters.action}
              onChange={(event) => {
                list.setFilter('action', event.target.value as ActionFilter);
              }}
            >
              <option value='all'>All actions</option>
              <option value='insert'>insert</option>
              <option value='update'>update</option>
              <option value='delete'>delete</option>
            </Select>
          </AdminFilterField>
          <AdminFilterField>
            <Select
              id='time-range'
              aria-label='Time range'
              value={list.filters.timeRange}
              onChange={(event) => {
                list.setFilter('timeRange', event.target.value);
              }}
            >
              {TIME_RANGES.map((range) => (
                <option key={range.value} value={range.value}>
                  {range.label}
                </option>
              ))}
            </Select>
          </AdminFilterField>
        </AdminFilterBar>
      }
      head={
        <>
          <AdminDataTableHeadCell>Table</AdminDataTableHeadCell>
          <AdminDataTableHeadCell priority='secondary'>Action</AdminDataTableHeadCell>
          <AdminDataTableHeadCell priority='secondary'>Actor</AdminDataTableHeadCell>
          <AdminDataTableHeadCell priority='tertiary'>Timestamp</AdminDataTableHeadCell>
        </>
      }
      renderCells={(item) => {
        const actor = getActor(item.user_id);
        return (
        <>
          <AdminDataTableCell>
            <AdminTableName>{item.table_name}</AdminTableName>
            <AdminDataTableCellMeta until='secondary'>
              <ActionBadge action={item.action} />
            </AdminDataTableCellMeta>
            <AdminDataTableCellMeta until='secondary' label='Actor' empty={false}>
              <AuditActorCaption actor={actor} />
            </AdminDataTableCellMeta>
            <AdminDataTableCellMeta until='tertiary' label='Timestamp' empty={!item.timestamp}>
              <AdminTableTime value={item.timestamp} />
            </AdminDataTableCellMeta>
          </AdminDataTableCell>
          <AdminDataTableCell priority='secondary'>
            <ActionBadge action={item.action} />
          </AdminDataTableCell>
          <AdminDataTableCell priority='secondary'>
            <AuditActorValue actor={actor} />
          </AdminDataTableCell>
          <AdminDataTableCell priority='tertiary'>
            <AdminTableTime value={item.timestamp} />
          </AdminDataTableCell>
        </>
        );
      }}
    />
    </div>
  );
}

function AuditLogDetail({ log, actor }: { log: AuditLog; actor: AuditActor }) {
  const oldValues = auditJsonRecord(log.old_values);
  const newValues = auditJsonRecord(log.new_values);

  return (
    <AdminEditorPanel>
      <AdminFieldGrid columns={2}>
        <AdminReadOnlyValue label='ID' mono>{log.id}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Timestamp'>{formatDateTime(log.timestamp)}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Table'>{log.table_name}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Record ID' mono>{log.record_id}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Action'>{formatAuditAction(log.action)}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Source'>{log.source?.trim() || '—'}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Actor'>
          <AuditActorValue actor={actor} />
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Request ID' mono>{log.request_id || '—'}</AdminReadOnlyValue>
        {log.changed_fields && log.changed_fields.length > 0 ? (
          <AdminReadOnlyValue label='Changed Fields' span='full'>{log.changed_fields.join(', ')}</AdminReadOnlyValue>
        ) : null}
        {oldValues ? (
          <AdminReadOnlyValue label='Old Values' span='full' mono>
            <AuditHighlightedJson
              aria-label='Old values JSON'
              className='max-h-40 overflow-auto rounded bg-red-50 p-2 text-red-900'
              emphasisClassName='bg-red-300'
              value={oldValues}
              counterpart={newValues}
              changedFields={log.changed_fields}
            />
          </AdminReadOnlyValue>
        ) : null}
        {newValues ? (
          <AdminReadOnlyValue label='New Values' span='full' mono>
            <AuditHighlightedJson
              aria-label='New values JSON'
              className='max-h-40 overflow-auto rounded bg-green-50 p-2 text-green-900'
              emphasisClassName='bg-green-300'
              value={newValues}
              counterpart={oldValues}
              changedFields={log.changed_fields}
            />
          </AdminReadOnlyValue>
        ) : null}
        {log.ip_address ? (
          <AdminReadOnlyValue label='IP'>{log.ip_address}</AdminReadOnlyValue>
        ) : null}
        {log.user_agent ? (
          <AdminReadOnlyValue label='User agent' span='full'>{log.user_agent}</AdminReadOnlyValue>
        ) : null}
      </AdminFieldGrid>
    </AdminEditorPanel>
  );
}
