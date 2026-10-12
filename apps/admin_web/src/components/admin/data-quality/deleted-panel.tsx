'use client';

import { useState } from 'react';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { useConfirmDialog } from '../../../hooks/use-confirm-dialog';
import { getAdminQueryClient } from '../../../lib/admin-query-client';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { ApiError } from '../../../lib/api-client';
import {
  forgetDeletedOrganization,
  listDeletedOrganizations,
  type DeletedOrganization,
} from '../../../lib/api-client-data-quality';
import { StatusBanner } from '../../status-banner';
import { AdminDataTableCell, AdminDataTableHeadCell } from '../../ui/admin-data-table';
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
      <ResourceTableShell
        ariaLabel='Deleted organizations'
        hasActions={false}
        filters={
          <AdminFilterBar>
            <AdminFilterField label='Name' htmlFor='deleted-org-name'>
              <Input
                id='deleted-org-name'
                value={list.filters.q}
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
            <AdminDataTableHeadCell priority='tertiary'>Source id</AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>{item.name}</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>{item.place_id || '—'}</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>{item.source || '—'}</AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>{item.source_id || '—'}</AdminDataTableCell>
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
        middleColumnCount={4}
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
      'A later import can create this organization.',
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
      </AdminFieldGrid>
    </AdminEditorPanel>
  );
}
