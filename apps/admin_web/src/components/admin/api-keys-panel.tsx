'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { useConfirmDialog } from '@/hooks/use-confirm-dialog';
import { useEntityPanelEditorShell } from '@/hooks/use-entity-panel-editor-shell';
import { usePaginatedList } from '@/hooks/use-paginated-list';
import { listResource } from '@/lib/api-client';
import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
} from '@/lib/api-client-api-keys';
import { getAdminQueryClient } from '@/lib/admin-query-client';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import { formatDateTime } from '@/lib/date-utils';
import type { ApiKey, Organization } from '@/types/admin';
import { DeleteIcon } from '@/components/icons/action-icons';
import { StatusBanner } from '@/components/status-banner';
import { AdminCreateButton } from '@/components/ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '@/components/ui/admin-data-table';
import { AdminDiscardChangesDialog } from '@/components/ui/admin-discard-changes-dialog';
import {
  AdminEditorActions,
  AdminEditorPanel,
} from '@/components/ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '@/components/ui/admin-field-grid';
import { AdminFilterBar } from '@/components/ui/admin-filter-bar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  ResourceTableShell,
  rowActions,
} from '@/components/ui/resource-table-shell';
import { Select } from '@/components/ui/select';
import { StatusBadge } from '@/components/ui/status-badge';

interface ApiKeyFormState {
  name: string;
  scope: 'read' | 'crud';
  org_id: string;
  expires_at: string;
}

const emptyForm: ApiKeyFormState = {
  name: '',
  scope: 'read',
  org_id: '',
  expires_at: '',
};

export function ApiKeysPanel() {
  const shell = useEntityPanelEditorShell({ paramName: 'api-key' });
  const { confirm, confirmDialog } = useConfirmDialog();
  const [formState, setFormState] = useState<ApiKeyFormState>(emptyForm);
  const [formError, setFormError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const list = usePaginatedList<ApiKey, Record<string, never>>({
    queryKey: adminQueryKeys.apiKeys(),
    defaultFilters: {},
    errorPrefix: 'Failed to load API keys',
    fetcher: async ({ cursor, limit }) => {
      const response = await listApiKeys(cursor ?? undefined, limit);
      return {
        items: response.items,
        nextCursor: response.next_cursor ?? null,
      };
    },
  });

  const organizationsQuery = useQuery(
    {
      queryKey: ['admin', 'organizations', 'api-key-picker'],
      queryFn: () => listResource<Organization>('organizations', undefined, 100),
    },
    getAdminQueryClient()
  );
  const organizations = organizationsQuery.data?.items ?? [];

  const orgNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const org of organizationsQuery.data?.items ?? []) {
      map.set(org.id, org.name);
    }
    return map;
  }, [organizationsQuery.data?.items]);

  const handleCreate = async () => {
    if (!formState.name.trim()) {
      setFormError('Name is required.');
      return;
    }
    let expiresAt: string | null = null;
    if (formState.expires_at) {
      const parsed = new Date(formState.expires_at);
      if (Number.isNaN(parsed.getTime())) {
        setFormError('Expiry date is invalid.');
        return;
      }
      if (parsed.getTime() <= Date.now()) {
        setFormError('Expiry date must be in the future.');
        return;
      }
      expiresAt = parsed.toISOString();
    }

    setIsSaving(true);
    setFormError('');
    setCopied(false);
    try {
      const created = await createApiKey({
        name: formState.name.trim(),
        scope: formState.scope,
        org_id: formState.org_id || null,
        expires_at: expiresAt,
      });
      setCreatedKey(created.api_key);
      setFormState(emptyForm);
      shell.clearDirty();
      list.setItems((prev) => [
        created,
        ...prev.filter((key) => key.id !== created.id),
      ]);
      shell.expanded.expand(created.id);
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : 'Failed to create API key.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  const requestRevoke = async (apiKey: ApiKey) => {
    const confirmed = await confirm(
      'Revoke API key?',
      `Revoke "${apiKey.name}"? Requests using this key will be ` +
        'rejected within a few minutes. This action cannot be undone.',
      { variant: 'danger', confirmLabel: 'Revoke Key' }
    );
    if (!confirmed) {
      return;
    }
    setRevokingId(apiKey.id);
    try {
      const revoked = await revokeApiKey(apiKey.id);
      list.setItems((prev) =>
        prev.map((key) => (key.id === revoked.id ? revoked : key))
      );
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : 'Failed to revoke API key.'
      );
    } finally {
      setRevokingId(null);
    }
  };

  const selected = list.items.find((key) => key.id === shell.selectedId);
  const showCreateForm = shell.expanded.isDraftOpen;

  const detail = showCreateForm ? (
    <AdminEditorPanel
      status={
        formError ? (
          <StatusBanner variant='error' title='Error'>
            {formError}
          </StatusBanner>
        ) : null
      }
      actions={
        <AdminEditorActions
          mode='create'
          onSubmit={() => {
            void handleCreate();
          }}
          isSaving={isSaving}
          submitLabel='Create Key'
          savingLabel='Creating…'
        />
      }
    >
      <AdminFieldGrid columns={4}>
        <AdminField label='Name' htmlFor='api-key-name' span={2} required>
          <Input
            id='api-key-name'
            placeholder='e.g. Partner Co integration'
            value={formState.name}
            onChange={(event) => {
              shell.markDirty();
              setFormState((prev) => ({ ...prev, name: event.target.value }));
            }}
          />
        </AdminField>
        <AdminField label='Scope' htmlFor='api-key-scope'>
          <Select
            id='api-key-scope'
            value={formState.scope}
            onChange={(event) => {
              shell.markDirty();
              setFormState((prev) => ({
                ...prev,
                scope: event.target.value as 'read' | 'crud',
              }));
            }}
          >
            <option value='read'>Read (query only)</option>
            <option value='crud'>CRUD (query and edit)</option>
          </Select>
        </AdminField>
        <AdminField label='Expiry (optional)' htmlFor='api-key-expires'>
          <Input
            id='api-key-expires'
            type='datetime-local'
            value={formState.expires_at}
            onChange={(event) => {
              shell.markDirty();
              setFormState((prev) => ({
                ...prev,
                expires_at: event.target.value,
              }));
            }}
          />
        </AdminField>
        <AdminField
          label='Organization'
          htmlFor='api-key-org'
          span='full'
          hint='Leave empty for a key that can access every organization.'
        >
          <Select
            id='api-key-org'
            value={formState.org_id}
            onChange={(event) => {
              shell.markDirty();
              setFormState((prev) => ({
                ...prev,
                org_id: event.target.value,
              }));
            }}
          >
            <option value=''>Full access (all organizations)</option>
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </Select>
        </AdminField>
      </AdminFieldGrid>
    </AdminEditorPanel>
  ) : selected ? (
    <AdminEditorPanel>
      <AdminFieldGrid columns={4}>
        <AdminField label='Name' htmlFor='api-key-detail-name' span={2}>
          <Input id='api-key-detail-name' value={selected.name} readOnly />
        </AdminField>
        <AdminField label='Scope' htmlFor='api-key-detail-scope'>
          <Input id='api-key-detail-scope' value={selected.scope} readOnly />
        </AdminField>
        <AdminField label='Status' htmlFor='api-key-detail-status'>
          <Input id='api-key-detail-status' value={selected.status} readOnly />
        </AdminField>
        <AdminField label='Prefix' htmlFor='api-key-detail-prefix' span={2}>
          <Input
            id='api-key-detail-prefix'
            value={`${selected.key_prefix}...`}
            readOnly
          />
        </AdminField>
        <AdminField label='Expires' htmlFor='api-key-detail-expires'>
          <Input
            id='api-key-detail-expires'
            value={
              selected.expires_at
                ? formatDateTime(selected.expires_at)
                : 'Never'
            }
            readOnly
          />
        </AdminField>
        <AdminField label='Last used' htmlFor='api-key-detail-used'>
          <Input
            id='api-key-detail-used'
            value={formatDateTime(selected.last_used_at)}
            readOnly
          />
        </AdminField>
      </AdminFieldGrid>
    </AdminEditorPanel>
  ) : null;

  return (
    <>
      <ResourceTableShell
        ariaLabel='API keys'
        rows={list.items}
        getLabel={(item) => item.name}
        middleColumnCount={4}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={list.loadMore}
        error={list.error}
        emptyLabel='No API keys found.'
        isExpanded={shell.expanded.isExpanded}
        onToggle={shell.expanded.toggle}
        isDraftOpen={shell.expanded.isDraftOpen}
        draftLabel='New API key'
        onToggleDraft={shell.expanded.collapse}
        detail={detail}
        toolbar={
          createdKey ? (
            <div className='mb-3'>
              <StatusBanner variant='success' title='API key created'>
                <span className='mb-2 block'>
                  Copy the key now. It is shown only once and cannot be
                  retrieved later.
                </span>
                <span className='flex flex-wrap items-center gap-2'>
                  <code
                    className='rounded bg-white px-2 py-1 font-mono text-xs'
                    data-testid='created-api-key'
                  >
                    {createdKey}
                  </code>
                  <Button
                    type='button'
                    size='sm'
                    variant='secondary'
                    onClick={() => {
                      void navigator.clipboard
                        .writeText(createdKey)
                        .then(() => setCopied(true))
                        .catch(() => setCopied(false));
                    }}
                  >
                    {copied ? 'Copied!' : 'Copy'}
                  </Button>
                  <Button
                    type='button'
                    size='sm'
                    variant='ghost'
                    onClick={() => setCreatedKey(null)}
                  >
                    Dismiss
                  </Button>
                </span>
              </StatusBanner>
            </div>
          ) : null
        }
        filters={
          <AdminFilterBar
            trailing={
              <AdminCreateButton
                label='New API key'
                active={shell.expanded.isDraftOpen}
                onClick={() => {
                  setFormState(emptyForm);
                  setFormError('');
                  shell.expanded.openDraft();
                }}
              />
            }
          />
        }
        head={
          <>
            <AdminDataTableHeadCell>Name</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Scope
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Organization
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Expires
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(apiKey) => (
          <>
            <AdminDataTableCell>
              <span className='font-medium'>{apiKey.name}</span>
              <AdminDataTableCellMeta>
                {apiKey.key_prefix}… · {apiKey.status}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <span className='text-xs font-medium uppercase text-slate-600'>
                {apiKey.scope}
              </span>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {apiKey.org_id
                ? (orgNameById.get(apiKey.org_id) ?? apiKey.org_id)
                : 'Full access'}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <StatusBadge status={apiKey.status} />
              <span className='mt-1 block text-xs text-slate-500'>
                {apiKey.expires_at
                  ? formatDateTime(apiKey.expires_at)
                  : 'Never'}
              </span>
            </AdminDataTableCell>
          </>
        )}
        renderActions={(apiKey) =>
          rowActions([
            {
              key: 'revoke',
              label: 'Revoke key',
              tone: 'danger',
              hidden: apiKey.status === 'revoked',
              disabled: revokingId === apiKey.id,
              icon: <DeleteIcon className='h-4 w-4' />,
              onClick: () => {
                void requestRevoke(apiKey);
              },
            },
          ])
        }
      />
      {confirmDialog}
      <AdminDiscardChangesDialog prompt={shell.expanded.discardPrompt} />
      {formError && !showCreateForm ? (
        <div className='mt-3'>
          <StatusBanner variant='error' title='Error'>
            {formError}
          </StatusBanner>
        </div>
      ) : null}
    </>
  );
}
