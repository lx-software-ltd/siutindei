'use client';

import { useQuery } from '@tanstack/react-query';
import { useQueryState } from 'nuqs';
import { useState } from 'react';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminTabLabel, formatAdminPageName } from '../../../lib/admin-page-name';
import { getAdminQueryClient } from '../../../lib/admin-query-client';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { ApiError } from '../../../lib/api-client';
import { listCognitoUsers } from '../../../lib/api-client-cognito';
import {
  acceptAllImportChanges,
  acceptImportChange,
  dismissImportChange,
  listImportChanges,
  type ImportChange,
} from '../../../lib/api-client-import-changes';
import { StatusBanner } from '../../status-banner';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import {
  adminTableText,
  AdminTableId,
  AdminTableName,
  AdminTableTime,
} from '../../ui/admin-table-value';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminFieldGrid } from '../../ui/admin-field-grid';
import { AdminReadOnlyValue } from '../../ui/admin-read-only-value';
import { Button } from '../../ui/button';
import { ResourceTableShell } from '../../ui/resource-table-shell';

const PAGE_NAME = formatAdminPageName('Data quality', adminTabLabel.importChanges);

export function ImportChangesPanel() {
  const [organization] = useQueryState('organization');
  const [org] = useQueryState('org');
  const orgId = organization || org || undefined;
  const expanded = useExpandedRecord({ paramName: 'import-change' });
  const list = usePaginatedList<ImportChange, { orgId: string }>({
    queryKey: adminQueryKeys.importChanges(orgId),
    defaultFilters: { orgId: orgId ?? '' },
    errorPrefix: 'Failed to load import changes',
    fetcher: async ({ cursor, limit }) => {
      const page = await listImportChanges({
        orgId,
        cursor: cursor ?? undefined,
        limit,
      });
      return { items: page.items, nextCursor: page.next_cursor ?? null };
    },
  });
  const open = list.items.find((item) => expanded.isExpanded(item.id)) ?? null;

  return (
    <>
      <h2 className='sr-only'>{PAGE_NAME}</h2>
      <ResourceTableShell
        ariaLabel={PAGE_NAME}
        hasActions={false}
        actions={
          orgId ? (
            <AcceptAll organizationId={orgId} onDone={() => void list.refetch()} />
          ) : null
        }
        head={
          <>
            <AdminDataTableHeadCell>Organization</AdminDataTableHeadCell>
            <AdminDataTableHeadCell>Record</AdminDataTableHeadCell>
            <AdminDataTableHeadCell>Field</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Current</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Proposed</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>When</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>Import job</AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <AdminTableName>{item.org_name || '—'}</AdminTableName>
              <AdminDataTableCellMeta until='secondary' label='Current'>
                {adminTableText(showValue(item.current_value))}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary' label='Proposed'>
                {adminTableText(showValue(item.proposed_value))}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary' label='When'>
                <AdminTableTime value={item.created_at} />
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta
                until='tertiary'
                label='Import job'
                empty={!item.import_job_id}
              >
                <AdminTableId>{item.import_job_id}</AdminTableId>
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell>
              <AdminTableName>{item.record_name || item.entity_type}</AdminTableName>
            </AdminDataTableCell>
            <AdminDataTableCell>{adminTableText(item.field)}</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {adminTableText(showValue(item.current_value))}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {adminTableText(showValue(item.proposed_value))}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <AdminTableTime value={item.created_at} />
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <AdminTableId>{item.import_job_id}</AdminTableId>
            </AdminDataTableCell>
          </>
        )}
        detail={
          open ? (
            <ImportChangeDetail
              item={open}
              onDone={() => {
                expanded.collapse();
                void list.refetch();
              }}
            />
          ) : null
        }
        rows={list.items}
        getLabel={(item) => `${item.record_name || item.entity_type} ${item.field}`}
        middleColumnCount={7}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={() => {
          void list.loadMore();
        }}
        error={list.error}
        emptyLabel='No import changes are waiting.'
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
      />
    </>
  );
}

function AcceptAll({
  organizationId,
  onDone,
}: {
  organizationId: string;
  onDone: () => void;
}) {
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  async function acceptAll() {
    setSaving(true);
    setError('');
    try {
      await acceptAllImportChanges({ org_id: organizationId });
      void getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.importChanges(organizationId),
      });
      onDone();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not accept these changes.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className='space-y-2'>
      {error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
      <Button
        type='button'
        variant='secondary'
        loading={saving}
        onClick={() => void acceptAll()}
      >
        Accept all for this organization
      </Button>
    </div>
  );
}

function ImportChangeDetail({
  item,
  onDone,
}: {
  item: ImportChange;
  onDone: () => void;
}) {
  const emails = useQuery({
    queryKey: ['admin', 'cognito-email-by-id'],
    queryFn: loadEmailById,
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState<'accept' | 'dismiss' | null>(null);

  async function decide(kind: 'accept' | 'dismiss') {
    setSaving(kind);
    setError('');
    try {
      if (kind === 'accept') {
        await acceptImportChange(item.id);
      } else {
        await dismissImportChange(item.id);
      }
      void getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.importChanges(item.org_id),
      });
      onDone();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not update this change.');
    } finally {
      setSaving(null);
    }
  }

  return (
    <AdminEditorPanel
      status={error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
      actions={
        <>
          <Button
            type='button'
            variant='secondary'
            loading={saving === 'accept'}
            onClick={() => void decide('accept')}
          >
            Accept
          </Button>
          <Button
            type='button'
            variant='secondary'
            loading={saving === 'dismiss'}
            onClick={() => void decide('dismiss')}
          >
            Keep mine
          </Button>
        </>
      }
    >
      <AdminFieldGrid columns={2}>
        <AdminReadOnlyValue label='Base' span='full'>
          {showValue(item.base_value)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Current' span='full'>
          {showValue(item.current_value)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Proposed' span='full'>
          {showValue(item.proposed_value)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Changed by'>
          {actorLabel(item, emails.data ?? {})}
        </AdminReadOnlyValue>
      </AdminFieldGrid>
    </AdminEditorPanel>
  );
}

function showValue(value: unknown): string {
  if (value == null || value === '') {
    return '—';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
}

function actorLabel(item: ImportChange, emailById: Record<string, string>): string {
  if (item.current_import_job_id) {
    return 'Import';
  }
  if (item.current_user_id) {
    return emailById[item.current_user_id] ?? 'Admin';
  }
  return 'System';
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
