'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { useExpandedRecord } from '@/hooks/use-expanded-record';
import { usePaginatedList } from '@/hooks/use-paginated-list';
import { ApiError, type AuditLogsFilters } from '@/lib/api-client';
import { listAuditLogs } from '@/lib/api-client-audit';
import { listCognitoUsers } from '@/lib/api-client-cognito';
import { formatAdminPageName } from '@/lib/admin-page-name';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import { formatAuditActor } from '@/lib/audit-actor';
import { formatDateTime } from '@/lib/date-utils';
import type { AuditLog } from '@/types/admin';
import { StatusBanner } from '@/components/status-banner';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '@/components/ui/admin-data-table';
import { AdminEditorPanel } from '@/components/ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '@/components/ui/admin-field-grid';
import {
  AdminFilterBar,
  AdminFilterField,
} from '@/components/ui/admin-filter-bar';
import { Input } from '@/components/ui/input';
import { ResourceTableShell } from '@/components/ui/resource-table-shell';
import { AdminReadOnlyValue } from '@/components/ui/admin-read-only-value';
import { Select } from '@/components/ui/select';
import { StatusBadge } from '@/components/ui/status-badge';
import { AdminTableId, AdminTableName, AdminTableTime } from '@/components/ui/admin-table-value';
import { Textarea } from '@/components/ui/textarea';

const PAGE_NAME = formatAdminPageName('Audit logs');

type ActionFilter = 'all' | 'INSERT' | 'UPDATE' | 'DELETE';

interface AuditLogListFilters {
  action: ActionFilter;
  table: string;
  timeRange: string;
  actor: string;
}

const defaultAuditLogFilters: AuditLogListFilters = {
  action: 'all',
  table: 'all',
  timeRange: '24h',
  actor: '',
};

const auditDebounceKeys: (keyof AuditLogListFilters)[] = ['actor'];

const AUDITABLE_TABLES = [
  'organizations',
  'locations',
  'activities',
  'activity_locations',
  'activity_pricing',
  'activity_schedule',
  'organization_access_requests',
  'organization_suggestions',
];

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

function formatJson(obj: Record<string, unknown> | null | undefined): string {
  if (!obj) {
    return '—';
  }
  return JSON.stringify(obj, null, 2);
}

function ActionBadge({ action }: { action: AuditLog['action'] }) {
  const tone = action === 'INSERT' ? 'green' : action === 'DELETE' ? 'red' : 'blue';

  return <StatusBadge status={action} tone={tone} label={action} />;
}

export function AuditLogsPanel() {
  const expanded = useExpandedRecord({ paramName: 'audit-log' });
  const [userLookupError, setUserLookupError] = useState('');
  const [userEmailById, setUserEmailById] = useState<Record<string, string>>({});
  const userLookupPromise = useRef<Promise<{
    emailById: Record<string, string>;
    idByEmail: Record<string, string>;
  }> | null>(null);
  const userLookupRef = useRef<{
    emailById: Record<string, string>;
    idByEmail: Record<string, string>;
  }>({ emailById: {}, idByEmail: {} });
  const isMountedRef = useRef(true);

  const loadCognitoUsers = useCallback(async (showError = false) => {
    if (Object.keys(userLookupRef.current.emailById).length > 0) {
      return userLookupRef.current;
    }
    if (userLookupPromise.current) {
      return userLookupPromise.current;
    }

    userLookupPromise.current = (async () => {
      try {
        const emailById: Record<string, string> = {};
        const idByEmail: Record<string, string> = {};
        let paginationToken: string | undefined;

        do {
          const response = await listCognitoUsers(paginationToken, 60);
          for (const user of response.items) {
            if (!user.email) {
              continue;
            }
            const normalizedEmail = user.email.trim().toLowerCase();
            emailById[user.sub] = user.email;
            if (!idByEmail[normalizedEmail]) {
              idByEmail[normalizedEmail] = user.sub;
            }
          }
          paginationToken = response.pagination_token ?? undefined;
        } while (paginationToken);

        userLookupRef.current = { emailById, idByEmail };
        if (isMountedRef.current) {
          setUserEmailById(emailById);
        }
        return userLookupRef.current;
      } catch (err) {
        if (showError && isMountedRef.current) {
          setUserLookupError(
            err instanceof ApiError ? err.message : 'Failed to load user directory.'
          );
        }
        return { emailById: {}, idByEmail: {} };
      } finally {
        userLookupPromise.current = null;
      }
    })();

    return userLookupPromise.current;
  }, []);

  const list = usePaginatedList<AuditLog, AuditLogListFilters>({
    queryKey: adminQueryKeys.auditLogs(),
    defaultFilters: defaultAuditLogFilters,
    debounceKeys: auditDebounceKeys,
    limit: 50,
    errorPrefix: 'Failed to load audit logs',
    fetcher: async ({ action, table, timeRange, actor, cursor, limit }) => {
      const filters: AuditLogsFilters = {};
      if (action !== 'all') {
        filters.action = action;
      }
      if (table !== 'all') {
        filters.table = table;
      }
      const since = getTimestamp(timeRange);
      if (since) {
        filters.since = since;
      }
      const actorEmail = actor.trim().toLowerCase();
      if (actorEmail) {
        const userMaps = await loadCognitoUsers(true);
        filters.user_id = userMaps.idByEmail[actorEmail] ?? '__no_match__';
      } else if (isMountedRef.current) {
        setUserLookupError('');
      }
      const response = await listAuditLogs(filters, cursor ?? undefined, limit);
      return {
        items: response.items,
        nextCursor: response.next_cursor ?? null,
      };
    },
  });

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    void loadCognitoUsers(false);
  }, [loadCognitoUsers]);

  const getActor = useCallback(
    (userId: string | null | undefined) => formatAuditActor(userId, userEmailById),
    [userEmailById]
  );

  const selected = list.items.find((item) => item.id === expanded.expandedId) ?? null;

  const detail = selected ? (
    <AuditLogDetail log={selected} actor={getActor(selected.user_id)} />
  ) : null;

  return (
    <div className='space-y-4'>
    <h2 className='sr-only'>{PAGE_NAME}</h2>
    {userLookupError ? (
      <StatusBanner kind='error'>
        {userLookupError}
      </StatusBanner>
    ) : null}
    <ResourceTableShell
      ariaLabel={PAGE_NAME}
      rows={list.items}
      getLabel={(item) => `${item.table_name} ${item.action}`}
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
              id='action-filter'
              aria-label='Action'
              value={list.filters.action}
              onChange={(event) => {
                list.setFilter('action', event.target.value as ActionFilter);
              }}
            >
              <option value='all'>All actions</option>
              <option value='INSERT'>Insert</option>
              <option value='UPDATE'>Update</option>
              <option value='DELETE'>Delete</option>
            </Select>
          </AdminFilterField>
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
          <AdminFilterField>
            <Input
              id='actor-filter'
              aria-label='Actor'
              type='text'
              placeholder='Actor email'
              value={list.filters.actor}
              onChange={(event) => {
                list.setFilter('actor', event.target.value);
              }}
            />
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
      renderCells={(item) => (
        <>
          <AdminDataTableCell>
            <AdminTableName>{item.table_name}</AdminTableName>
            <AdminDataTableCellMeta until='secondary'>
              <ActionBadge action={item.action} />
            </AdminDataTableCellMeta>
            <AdminDataTableCellMeta until='secondary'>
              <AdminTableId>{getActor(item.user_id)}</AdminTableId>
            </AdminDataTableCellMeta>
            <AdminDataTableCellMeta until='tertiary'>
              <AdminTableTime value={item.timestamp} />
            </AdminDataTableCellMeta>
          </AdminDataTableCell>
          <AdminDataTableCell priority='secondary'>
            <ActionBadge action={item.action} />
          </AdminDataTableCell>
          <AdminDataTableCell priority='secondary'>
            <AdminTableId>{getActor(item.user_id)}</AdminTableId>
          </AdminDataTableCell>
          <AdminDataTableCell priority='tertiary'>
            <AdminTableTime value={item.timestamp} />
          </AdminDataTableCell>
        </>
      )}
    />
    </div>
  );
}

function AuditLogDetail({ log, actor }: { log: AuditLog; actor: string }) {
  const hasOldValues = Boolean(log.old_values && Object.keys(log.old_values).length > 0);
  const hasNewValues = Boolean(log.new_values && Object.keys(log.new_values).length > 0);

  return (
    <AdminEditorPanel>
      <AdminFieldGrid columns={2}>
        <AdminReadOnlyValue label='ID' mono>{log.id}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Timestamp'>{formatDateTime(log.timestamp)}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Table'>{log.table_name}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Record ID' mono>{log.record_id}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Action'>{log.action}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Source'>{log.source}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Actor'>{actor}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Request ID' mono>{log.request_id || '—'}</AdminReadOnlyValue>
        {log.changed_fields && log.changed_fields.length > 0 ? (
          <AdminReadOnlyValue label='Changed Fields' span='full'>{log.changed_fields.join(', ')}</AdminReadOnlyValue>
        ) : null}
        {hasOldValues ? (
          <AdminReadOnlyValue label='Old Values' span='full' mono>
            <span className='block max-h-40 overflow-auto rounded bg-red-50 p-2 text-red-900'>
              {formatJson(log.old_values)}
            </span>
          </AdminReadOnlyValue>
        ) : null}
        {hasNewValues ? (
          <AdminReadOnlyValue label='New Values' span='full' mono>
            <span className='block max-h-40 overflow-auto rounded bg-green-50 p-2 text-green-900'>
              {formatJson(log.new_values)}
            </span>
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
