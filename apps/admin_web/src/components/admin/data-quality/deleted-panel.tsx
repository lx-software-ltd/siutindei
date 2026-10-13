'use client';

import { useState } from 'react';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { useConfirmDialog } from '../../../hooks/use-confirm-dialog';
import { adminTabLabel, formatAdminPageName } from '../../../lib/admin-page-name';
import { getAdminQueryClient } from '../../../lib/admin-query-client';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { ApiError } from '../../../lib/api-client';
import { formatDateTime } from '../../../lib/date-utils';
import {
  forgetDeletedOrganization,
  listDeletedOrganizations,
  type DeletedOrganization,
} from '../../../lib/api-client-data-quality';
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
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { AdminReadOnlyValue } from '../../ui/admin-read-only-value';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { ResourceTableShell } from '../../ui/resource-table-shell';

interface DeletedFilters {
  q: string;
}

const DEFAULT_FILTERS: DeletedFilters = { q: '' };
const PAGE_NAME = formatAdminPageName('Data quality', adminTabLabel.deleted);

export function DeletedPanel() {
  const expanded = useExpandedRecord({ paramName: 'deleted-org' });
  const { confirm, confirmDialog } = useConfirmDialog();
  const list = usePaginatedList<DeletedOrganization, DeletedFilters>({
    queryKey: adminQueryKeys.deletedOrganizations(),
    defaultFilters: DEFAULT_FILTERS,
    debounceKeys: ['q'],
    errorPrefix: 'Failed to load deleted organizations',
    fetcher: async ({ cursor, limit, q }) => {
      const page = await listDeletedOrganizations({
        cursor: cursor ?? undefined,
        limit,
        q: q || undefined,
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
        filters={
          <AdminFilterBar>
            <AdminFilterField>
              <Input
                id='deleted-org-name'
                aria-label='Name'
                value={list.filters.q}
                placeholder='Name'
                onChange={(event) => list.setFilter('q', event.target.value)}
              />
            </AdminFilterField>
          </AdminFilterBar>
        }
        head={
          <>
            <AdminDataTableHeadCell>Name</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Place id</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Source</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Deleted</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>Source id</AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <AdminTableName>{item.name}</AdminTableName>
              <AdminDataTableCellMeta until='secondary' label='Place id' empty={!item.place_id}>
                <AdminTableId>{item.place_id}</AdminTableId>
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary' label='Source'>
                {adminTableText(item.source)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary' label='Deleted' empty={!item.deleted_at}>
                <AdminTableTime value={item.deleted_at} />
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='tertiary' label='Source id' empty={!item.source_id}>
                <AdminTableId>{item.source_id}</AdminTableId>
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <AdminTableId>{item.place_id}</AdminTableId>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {adminTableText(item.source)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <AdminTableTime value={item.deleted_at} />
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <AdminTableId>{item.source_id}</AdminTableId>
            </AdminDataTableCell>
          </>
        )}
        detail={
          open ? (
            <DeletedDetail
              item={open}
              onForgot={() => {
                expanded.collapse();
                void list.refetch();
              }}
              confirm={confirm}
            />
          ) : null
        }
        rows={list.items}
        getLabel={(item) => item.name || 'Deleted organization'}
        middleColumnCount={5}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={() => {
          void list.loadMore();
        }}
        error={list.error}
        emptyLabel='No deleted organizations are blocking import.'
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
      />
      {confirmDialog}
    </>
  );
}

function forgetMessage(item: DeletedOrganization): string {
  const again =
    'Run the import again, including the same file. The earlier result is not reused.';
  if (item.also_forgets && item.also_forgets.length > 0) {
    return `This also allows import of ${item.also_forgets.join(', ')}. ${again}`;
  }
  if (item.was_merge) {
    return `Only this previously merged identity can be imported again. ${again}`;
  }
  return `A later import can create this organization. ${again}`;
}

function DeletedDetail({
  item,
  onForgot,
  confirm,
}: {
  item: DeletedOrganization;
  onForgot: () => void;
  confirm: (title: string, message: string, options?: { confirmLabel?: string; variant?: 'danger' | 'default' }) => Promise<boolean>;
}) {
  const [error, setError] = useState('');
  const [forgetting, setForgetting] = useState(false);

  async function forget() {
    const accepted = await confirm(
      'Allow import again',
      forgetMessage(item),
      { confirmLabel: 'Allow import', variant: 'danger' }
    );
    if (!accepted) {
      return;
    }
    setForgetting(true);
    setError('');
    try {
      await forgetDeletedOrganization(item.id);
      void getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.deletedOrganizations(),
      });
      onForgot();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not forget this organization.');
    } finally {
      setForgetting(false);
    }
  }

  return (
    <AdminEditorPanel
      status={error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
      actions={
        <Button type='button' variant='danger' loading={forgetting} onClick={() => void forget()}>
          Forget
        </Button>
      }
    >
      <AdminFieldGrid columns={2}>
        <AdminReadOnlyValue label='Names' span='full'>
          {item.names.join(', ') || '—'}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Place id' mono>
          {item.place_id || '—'}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Source'>{item.source || '—'}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Source id' mono>
          {item.source_id || '—'}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Deleted by'>{item.deleted_by || '—'}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Deleted'>{formatDateTime(item.deleted_at)}</AdminReadOnlyValue>
        {item.was_merge ? (
          <AdminReadOnlyValue label='History' span='full'>
            Merged into an organization that was later deleted.
          </AdminReadOnlyValue>
        ) : null}
        {item.also_forgets && item.also_forgets.length > 0 ? (
          <AdminReadOnlyValue label='Also released' span='full'>
            {item.also_forgets.join(', ')}
          </AdminReadOnlyValue>
        ) : null}
      </AdminFieldGrid>
    </AdminEditorPanel>
  );
}
