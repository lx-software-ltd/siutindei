'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { useExpandedRecord } from '@/hooks/use-expanded-record';
import { usePaginatedList } from '@/hooks/use-paginated-list';
import { ApiError, type AuditLogsFilters } from '@/lib/api-client';
import { listAuditLogs } from '@/lib/api-client-audit';
import { listCognitoUsers } from '@/lib/api-client-cognito';
import { adminQueryKeys } from '@/lib/admin-query-keys';
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
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';

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

/** Narrow enough that Action, Table, Time range, and Actor share one desktop row. */
const filterFieldClass = '!min-w-[8.5rem] sm:!flex-1 sm:!basis-0';

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

function formatGmtOffset(date: Date = new Date()) {
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const absMinutes = Math.abs(offsetMinutes);
  const hours = Math.floor(absMinutes / 60);
  const minutes = absMinutes % 60;
  const minuteSuffix = minutes ? `:${minutes.toString().padStart(2, '0')}` : '';
  return `GMT${sign}${hours}${minuteSuffix}`;
}

function formatJson(obj: Record<string, unknown> | null | undefined): string {
  if (!obj) {
    return '—';
  }
  return JSON.stringify(obj, null, 2);
}

function ActionBadge({ action }: { action: AuditLog['action'] }) {
  const colors = {
    INSERT: 'bg-green-100 text-green-800',
    UPDATE: 'bg-blue-100 text-blue-800',
    DELETE: 'bg-red-100 text-red-800',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors[action]}`}
    >
      {action}
    </span>
  );
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
    queryKey: adminQueryKeys.auditLogs(defaultAuditLogFilters),
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

  const getUserEmail = useCallback(
    (userId: string | null | undefined) => {
      if (!userId) {
        return '—';
      }
      return userEmailById[userId] || '—';
    },
    [userEmailById]
  );

  const selected = list.items.find((item) => item.id === expanded.expandedId) ?? null;
  const timestampHeader = `Timestamp ${formatGmtOffset()}`;

  const detail = selected ? (
    <AuditLogDetail log={selected} userEmail={getUserEmail(selected.user_id)} />
  ) : null;

  return (
    <ResourceTableShell
      ariaLabel='Audit logs'
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
      toolbar={
        userLookupError ? (
          <div className='mb-3'>
            <StatusBanner variant='error' title='User Lookup'>
              {userLookupError}
            </StatusBanner>
          </div>
        ) : null
      }
      filters={
        <AdminFilterBar summary={`Showing ${list.items.length} entries`}>
          <AdminFilterField label='Action' htmlFor='action-filter' className={filterFieldClass}>
            <Select
              id='action-filter'
              value={list.filters.action}
              onChange={(event) => {
                list.setFilter('action', event.target.value as ActionFilter);
              }}
            >
              <option value='all'>All Actions</option>
              <option value='INSERT'>Insert</option>
              <option value='UPDATE'>Update</option>
              <option value='DELETE'>Delete</option>
            </Select>
          </AdminFilterField>
          <AdminFilterField label='Table' htmlFor='table-filter' className={filterFieldClass}>
            <Select
              id='table-filter'
              value={list.filters.table}
              onChange={(event) => {
                list.setFilter('table', event.target.value);
              }}
            >
              <option value='all'>All Tables</option>
              {AUDITABLE_TABLES.map((table) => (
                <option key={table} value={table}>
                  {table}
                </option>
              ))}
            </Select>
          </AdminFilterField>
          <AdminFilterField label='Time range' htmlFor='time-range' className={filterFieldClass}>
            <Select
              id='time-range'
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
          <AdminFilterField label='Actor' htmlFor='actor-filter' className={filterFieldClass}>
            <Input
              id='actor-filter'
              type='text'
              placeholder='Filter by email...'
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
          <AdminDataTableHeadCell priority='secondary'>User Email</AdminDataTableHeadCell>
          <AdminDataTableHeadCell priority='tertiary'>{timestampHeader}</AdminDataTableHeadCell>
        </>
      }
      renderCells={(item) => (
        <>
          <AdminDataTableCell>
            <span className='font-medium'>{item.table_name}</span>
            <AdminDataTableCellMeta>
              {item.changed_fields?.length ? item.changed_fields.join(', ') : '—'}
            </AdminDataTableCellMeta>
          </AdminDataTableCell>
          <AdminDataTableCell priority='secondary'>
            <ActionBadge action={item.action} />
          </AdminDataTableCell>
          <AdminDataTableCell priority='secondary'>
            <span className='font-mono text-xs text-slate-600'>{getUserEmail(item.user_id)}</span>
          </AdminDataTableCell>
          <AdminDataTableCell priority='tertiary'>
            <span className='text-slate-600'>{formatDateTime(item.timestamp)}</span>
          </AdminDataTableCell>
        </>
      )}
    />
  );
}

function AuditLogDetail({ log, userEmail }: { log: AuditLog; userEmail: string }) {
  const fieldId = (name: string) => `audit-${log.id}-${name}`;
  const hasOldValues = Boolean(log.old_values && Object.keys(log.old_values).length > 0);
  const hasNewValues = Boolean(log.new_values && Object.keys(log.new_values).length > 0);

  return (
    <AdminEditorPanel>
      <AdminFieldGrid columns={2}>
        <AdminField label='ID' htmlFor={fieldId('id')}>
          <Input id={fieldId('id')} value={log.id} readOnly />
        </AdminField>
        <AdminField label='Timestamp' htmlFor={fieldId('timestamp')}>
          <Input id={fieldId('timestamp')} value={formatDateTime(log.timestamp)} readOnly />
        </AdminField>
        <AdminField label='Table' htmlFor={fieldId('table')}>
          <Input id={fieldId('table')} value={log.table_name} readOnly />
        </AdminField>
        <AdminField label='Record ID' htmlFor={fieldId('record')}>
          <Input id={fieldId('record')} value={log.record_id} readOnly />
        </AdminField>
        <AdminField label='Action' htmlFor={fieldId('action')}>
          <Input id={fieldId('action')} value={log.action} readOnly />
        </AdminField>
        <AdminField label='Source' htmlFor={fieldId('source')}>
          <Input id={fieldId('source')} value={log.source} readOnly />
        </AdminField>
        <AdminField label='User Email' htmlFor={fieldId('email')}>
          <Input id={fieldId('email')} value={userEmail} readOnly />
        </AdminField>
        <AdminField label='Request ID' htmlFor={fieldId('request')}>
          <Input id={fieldId('request')} value={log.request_id || '—'} readOnly />
        </AdminField>
        {log.changed_fields && log.changed_fields.length > 0 ? (
          <AdminField label='Changed Fields' htmlFor={fieldId('changed')} span='full'>
            <Input id={fieldId('changed')} value={log.changed_fields.join(', ')} readOnly />
          </AdminField>
        ) : null}
        {hasOldValues ? (
          <AdminField label='Old Values' htmlFor={fieldId('old')} span='full'>
            <Textarea
              id={fieldId('old')}
              readOnly
              rows={6}
              value={formatJson(log.old_values)}
              className='max-h-40 bg-red-50 font-mono text-xs text-red-900'
            />
          </AdminField>
        ) : null}
        {hasNewValues ? (
          <AdminField label='New Values' htmlFor={fieldId('new')} span='full'>
            <Textarea
              id={fieldId('new')}
              readOnly
              rows={6}
              value={formatJson(log.new_values)}
              className='max-h-40 bg-green-50 font-mono text-xs text-green-900'
            />
          </AdminField>
        ) : null}
        {log.ip_address ? (
          <AdminField label='IP' htmlFor={fieldId('ip')}>
            <Input id={fieldId('ip')} value={log.ip_address} readOnly />
          </AdminField>
        ) : null}
        {log.user_agent ? (
          <AdminField label='User agent' htmlFor={fieldId('agent')} span='full'>
            <Input id={fieldId('agent')} value={log.user_agent} readOnly />
          </AdminField>
        ) : null}
      </AdminFieldGrid>
    </AdminEditorPanel>
  );
}
