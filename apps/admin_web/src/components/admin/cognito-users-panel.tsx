'use client';

import { useCallback, useState } from 'react';

import { useConfirmDialog } from '@/hooks/use-confirm-dialog';
import { useExpandedRecord } from '@/hooks/use-expanded-record';
import { usePaginatedList } from '@/hooks/use-paginated-list';
import { ApiError } from '@/lib/api-client';
import {
  addUserToGroup,
  deleteCognitoUser,
  listCognitoUsers,
  removeUserFromGroup,
} from '@/lib/api-client-cognito';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import { formatDate, formatDateTime } from '@/lib/date-utils';
import type { CognitoUser } from '@/types/admin';
import { useAuth } from '@/components/auth-provider';
import { DeleteIcon } from '@/components/icons/action-icons';
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
import { ResourceTableShell, rowActions } from '@/components/ui/resource-table-shell';
import { Textarea } from '@/components/ui/textarea';
import {
  BriefcaseIcon,
  IdentityProviderBadge,
  RoleBadge,
  ShieldIcon,
} from './cognito-users/badges';

interface CognitoUserRow extends CognitoUser {
  id: string;
}

export function CognitoUsersPanel() {
  const { user: currentUser } = useAuth();
  const expanded = useExpandedRecord({ paramName: 'user' });
  const { confirm, confirmDialog } = useConfirmDialog();
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const list = usePaginatedList<CognitoUserRow, Record<string, never>>({
    queryKey: adminQueryKeys.cognitoUsers(),
    defaultFilters: {},
    limit: 50,
    errorPrefix: 'Failed to load users',
    fetcher: async ({ cursor, limit }) => {
      const response = await listCognitoUsers(cursor ?? undefined, limit);
      return {
        items: response.items.map((user) => ({ ...user, id: user.sub })),
        nextCursor: response.pagination_token ?? null,
      };
    },
  });

  const handleToggleRole = async (
    targetUser: CognitoUserRow,
    role: 'admin' | 'manager',
    currentlyHasRole: boolean
  ) => {
    if (!targetUser.username) {
      setActionError('User has no username');
      return;
    }

    const actionKey = `${targetUser.sub}-${role}`;
    setActionLoading(actionKey);
    setActionError('');

    try {
      if (currentlyHasRole) {
        await removeUserFromGroup(targetUser.username, role);
      } else {
        await addUserToGroup(targetUser.username, role);
      }
      list.setItems((prev) =>
        prev.map((user) => {
          if (user.sub !== targetUser.sub) {
            return user;
          }
          const groups = currentlyHasRole
            ? (user.groups || []).filter((group) => group !== role)
            : [...(user.groups || []), role];
          return { ...user, groups };
        })
      );
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : `Failed to ${currentlyHasRole ? 'remove' : 'add'} ${role} role.`;
      setActionError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteUser = async (targetUser: CognitoUserRow) => {
    if (!targetUser.username) {
      setActionError('User has no username');
      return;
    }

    const actionKey = `delete-${targetUser.sub}`;
    setActionLoading(actionKey);
    setActionError('');

    try {
      await deleteCognitoUser(targetUser.username);
      list.setItems((prev) => prev.filter((user) => user.sub !== targetUser.sub));
      if (expanded.isExpanded(targetUser.id)) {
        expanded.collapse();
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to delete user.';
      setActionError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const requestDeleteUser = async (targetUser: CognitoUserRow) => {
    const identifier = targetUser.email || targetUser.username || 'this user';
    const confirmed = await confirm(
      'Delete user?',
      `Delete ${identifier}? This action cannot be undone.`,
      { variant: 'danger', confirmLabel: 'Delete User' }
    );
    if (!confirmed) {
      return;
    }
    await handleDeleteUser(targetUser);
  };

  const isCurrentUser = useCallback(
    (cognitoUser: CognitoUser) => currentUser?.subject === cognitoUser.sub,
    [currentUser?.subject]
  );

  const filteredUsers = list.items.filter((cognitoUser) => {
    if (!searchQuery.trim()) {
      return true;
    }
    const query = searchQuery.toLowerCase();
    const groupsStr = cognitoUser.groups?.join(', ')?.toLowerCase() || '';
    return (
      cognitoUser.email?.toLowerCase().includes(query) ||
      cognitoUser.username?.toLowerCase().includes(query) ||
      cognitoUser.name?.toLowerCase().includes(query) ||
      cognitoUser.status?.toLowerCase().includes(query) ||
      groupsStr.includes(query)
    );
  });

  const selected = list.items.find((item) => item.id === expanded.expandedId) ?? null;

  return (
    <>
      <ResourceTableShell
        ariaLabel='Users'
        rows={filteredUsers}
        getLabel={(item) => item.email || item.username || 'Unknown'}
        middleColumnCount={4}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={list.loadMore}
        error={list.error}
        emptyLabel={searchQuery.trim() ? 'No users match your search.' : 'No users found.'}
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={selected ? <UserAttributesDetail user={selected} /> : null}
        toolbar={
          actionError ? (
            <div className='mb-3'>
              <StatusBanner variant='error' title='Action Failed'>
                {actionError}
              </StatusBanner>
            </div>
          ) : null
        }
        filters={
          <AdminFilterBar>
            <AdminFilterField label='Search' htmlFor='cognito-user-search'>
              <Input
                id='cognito-user-search'
                placeholder='Search users...'
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </AdminFilterField>
          </AdminFilterBar>
        }
        head={
          <>
            <AdminDataTableHeadCell>Email</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Roles</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Last Login</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>Created</AdminDataTableHeadCell>
          </>
        }
        renderCells={(cognitoUser) => {
          const isCurrent = isCurrentUser(cognitoUser);
          const hasAdminRole = cognitoUser.groups?.includes('admin') || false;
          const hasManagerRole = cognitoUser.groups?.includes('manager') || false;
          return (
            <>
              <AdminDataTableCell>
                <div className='min-w-0'>
                  <div className='flex items-center gap-2'>
                    <span className='truncate font-medium'>
                      {cognitoUser.email || cognitoUser.username || 'Unknown'}
                    </span>
                    <IdentityProviderBadge username={cognitoUser.username} />
                    {isCurrent ? (
                      <span className='rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-600'>
                        You
                      </span>
                    ) : null}
                  </div>
                  {cognitoUser.name ? (
                    <div className='text-xs text-slate-500'>{cognitoUser.name}</div>
                  ) : null}
                  <AdminDataTableCellMeta>
                    {hasAdminRole && hasManagerRole
                      ? 'Admin, Manager'
                      : hasAdminRole
                        ? 'Admin'
                        : hasManagerRole
                          ? 'Manager'
                          : 'No roles'}
                    {' · '}
                    {formatDateTime(cognitoUser.last_auth_time)}
                  </AdminDataTableCellMeta>
                  <AdminDataTableCellMeta until='tertiary'>
                    {formatDate(cognitoUser.created_at)}
                  </AdminDataTableCellMeta>
                </div>
              </AdminDataTableCell>
              <AdminDataTableCell priority='secondary'>
                <div className='flex gap-1'>
                  <RoleBadge role='admin' isActive={hasAdminRole} />
                  <RoleBadge role='manager' isActive={hasManagerRole} />
                </div>
              </AdminDataTableCell>
              <AdminDataTableCell priority='secondary'>
                <span className='text-slate-600'>{formatDateTime(cognitoUser.last_auth_time)}</span>
              </AdminDataTableCell>
              <AdminDataTableCell priority='tertiary'>
                <span className='text-slate-600'>{formatDate(cognitoUser.created_at)}</span>
              </AdminDataTableCell>
            </>
          );
        }}
        renderActions={(cognitoUser) => {
          if (isCurrentUser(cognitoUser)) {
            return (
              <span className='text-xs text-slate-400'>Cannot modify your own account</span>
            );
          }
          const hasAdminRole = cognitoUser.groups?.includes('admin') || false;
          const hasManagerRole = cognitoUser.groups?.includes('manager') || false;
          return rowActions([
            {
              key: 'admin',
              label: hasAdminRole ? 'Remove Admin' : 'Make Admin',
              tone: hasAdminRole ? 'danger' : 'default',
              disabled: actionLoading === `${cognitoUser.sub}-admin`,
              icon: <ShieldIcon className='h-4 w-4' />,
              onClick: () => {
                void handleToggleRole(cognitoUser, 'admin', hasAdminRole);
              },
            },
            {
              key: 'manager',
              label: hasManagerRole ? 'Remove Manager' : 'Make Manager',
              tone: hasManagerRole ? 'danger' : 'default',
              disabled: actionLoading === `${cognitoUser.sub}-manager`,
              icon: <BriefcaseIcon className='h-4 w-4' />,
              onClick: () => {
                void handleToggleRole(cognitoUser, 'manager', hasManagerRole);
              },
            },
            {
              key: 'delete',
              label: 'Delete User',
              tone: 'danger',
              disabled: actionLoading === `delete-${cognitoUser.sub}`,
              icon: <DeleteIcon className='h-4 w-4' />,
              onClick: () => {
                void requestDeleteUser(cognitoUser);
              },
            },
          ]);
        }}
      />
      {confirmDialog}
    </>
  );
}

function UserAttributesDetail({ user }: { user: CognitoUserRow }) {
  const attributes = user.attributes ?? {};
  const attributeEntries = Object.entries(attributes).sort((a, b) => a[0].localeCompare(b[0]));
  const fieldId = (name: string) => `cognito-${user.id}-${name}`;

  return (
    <AdminEditorPanel>
      <AdminFieldGrid columns={2}>
        <AdminField label='Email' htmlFor={fieldId('email')}>
          <Input id={fieldId('email')} value={user.email || '—'} readOnly />
        </AdminField>
        <AdminField label='Username' htmlFor={fieldId('username')}>
          <Input id={fieldId('username')} value={user.username || '—'} readOnly />
        </AdminField>
        <AdminField label='Status' htmlFor={fieldId('status')}>
          <Input id={fieldId('status')} value={user.status} readOnly />
        </AdminField>
        <AdminField label='Groups' htmlFor={fieldId('groups')}>
          <Input id={fieldId('groups')} value={user.groups?.join(', ') || '—'} readOnly />
        </AdminField>
        <AdminField label='Created' htmlFor={fieldId('created')}>
          <Input id={fieldId('created')} value={user.created_at || '—'} readOnly />
        </AdminField>
        <AdminField label='Last Login' htmlFor={fieldId('login')}>
          <Input id={fieldId('login')} value={user.last_auth_time || '—'} readOnly />
        </AdminField>
        <AdminField label='Raw Attributes' htmlFor={fieldId('attributes')} span='full'>
          <Textarea
            id={fieldId('attributes')}
            readOnly
            rows={attributeEntries.length === 0 ? 2 : 8}
            value={
              attributeEntries.length === 0
                ? 'No attributes found.'
                : JSON.stringify(attributes, null, 2)
            }
            className='max-h-64 bg-slate-50 font-mono text-xs text-slate-700'
          />
        </AdminField>
      </AdminFieldGrid>
    </AdminEditorPanel>
  );
}
