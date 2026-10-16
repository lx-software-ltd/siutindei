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
import { formatAdminPageName } from '@/lib/admin-page-name';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import { formatDateTime } from '@/lib/date-utils';
import type { CognitoUser } from '@/types/admin';
import { useAuth } from '@/components/auth-provider';
import { BriefcaseIcon, DeleteIcon, ShieldIcon } from '@/components/icons/action-icons';
import { StatusBanner } from '@/components/status-banner';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '@/components/ui/admin-data-table';
import { AdminEditorPanel } from '@/components/ui/admin-editor-panel';
import { AdminReadOnlyValue } from '@/components/ui/admin-read-only-value';
import { AdminFieldGrid } from '@/components/ui/admin-field-grid';
import { ResourceTableShell, rowActions } from '@/components/ui/resource-table-shell';
import {
  ADMIN_TABLE_EMPTY,
  AdminTableName,
  AdminTableTime,
} from '@/components/ui/admin-table-value';
import { StatusBadge } from '@/components/ui/status-badge';
import {
  assignedUserRoles,
  formatRoleLabel,
  getIdentityProvider,
  IdentityProviderBadge,
  RoleBadge,
  type UserRole,
} from './cognito-users/badges';

const PAGE_NAME = formatAdminPageName('Users');

function UserRoleMarks({ roles }: { roles: UserRole[] }) {
  if (roles.length === 0) {
    return ADMIN_TABLE_EMPTY;
  }
  return (
    <span className='inline-flex flex-wrap gap-1'>
      {roles.map((role) => (
        <RoleBadge key={role} role={role} />
      ))}
    </span>
  );
}

interface CognitoUserRow extends CognitoUser {
  id: string;
}

export function CognitoUsersPanel() {
  const { user: currentUser } = useAuth();
  const expanded = useExpandedRecord({ paramName: 'user' });
  const { confirm, confirmDialog } = useConfirmDialog();
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState('');

  const list = usePaginatedList<CognitoUserRow, Record<string, never>>({
    queryKey: adminQueryKeys.cognitoUsers(),
    defaultFilters: {},
    limit: 50,
    errorPrefix: 'Failed to load users',
    fetcher: async ({ cursor, limit }) => {
      const response = await listCognitoUsers(
        cursor ?? undefined,
        limit,
        undefined,
        'managed_organizations'
      );
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

  const selected = list.items.find((item) => item.id === expanded.expandedId) ?? null;

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>{PAGE_NAME}</h2>
      {actionError ? (
        <StatusBanner kind='error'>
          {actionError}
        </StatusBanner>
      ) : null}
      <ResourceTableShell
        ariaLabel={PAGE_NAME}
        rows={list.items}
        getLabel={(item) => item.email || item.username || 'User'}
        middleColumnCount={3}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={list.loadMore}
        error={list.error}
        emptyLabel='No users found.'
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={selected ? <UserAttributesDetail user={selected} /> : null}
        head={
          <>
            <AdminDataTableHeadCell>Email</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Roles</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>Last Login</AdminDataTableHeadCell>
          </>
        }
        renderCells={(cognitoUser) => {
          const isCurrent = isCurrentUser(cognitoUser);
          const roles = assignedUserRoles(cognitoUser.groups);
          return (
            <>
              <AdminDataTableCell>
                <span className='inline-flex min-w-0 items-center gap-1.5'>
                  <AdminTableName>
                    {cognitoUser.email || cognitoUser.username || ''}
                  </AdminTableName>
                  <IdentityProviderBadge username={cognitoUser.username} />
                  {isCurrent ? <StatusBadge status='you' tone='slate' label='You' /> : null}
                </span>
                <AdminDataTableCellMeta until='secondary' label='Roles' empty={roles.length === 0}>
                  <UserRoleMarks roles={roles} />
                </AdminDataTableCellMeta>
                <AdminDataTableCellMeta until='tertiary' label='Last Login' empty={!cognitoUser.last_auth_time}>
                  <AdminTableTime value={cognitoUser.last_auth_time} />
                </AdminDataTableCellMeta>
              </AdminDataTableCell>
              <AdminDataTableCell priority='secondary'>
                <UserRoleMarks roles={roles} />
              </AdminDataTableCell>
              <AdminDataTableCell priority='tertiary'>
                <AdminTableTime value={cognitoUser.last_auth_time} />
              </AdminDataTableCell>
            </>
          );
        }}
        renderActions={(cognitoUser) => {
          if (isCurrentUser(cognitoUser)) {
            return <span className='sr-only'>Cannot modify your own account</span>;
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
    </div>
  );
}

function ManagedOrganizations({
  organizations,
}: {
  organizations: CognitoUser['managed_organizations'];
}) {
  if (!organizations?.length) {
    return '—';
  }
  return (
    <ul className='list-disc space-y-1 pl-5'>
      {organizations.map((organization) => (
        <li key={organization.id}>{organization.name}</li>
      ))}
    </ul>
  );
}

function UserAttributesDetail({ user }: { user: CognitoUserRow }) {
  const status = user.status.trim().toLowerCase();
  return (
    <AdminEditorPanel>
      <AdminFieldGrid columns={2}>
        <AdminReadOnlyValue label='Email'>{user.email || '—'}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Username' mono>
          {user.username || '—'}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Name'>{user.name?.trim() || '—'}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Provider'>
          {getIdentityProvider(user.username)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Status'>{status || '—'}</AdminReadOnlyValue>
        <AdminReadOnlyValue label='Roles'>
          {user.groups?.length
            ? user.groups.map((group) => formatRoleLabel(group)).join(', ')
            : '—'}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Created'>
          {formatDateTime(user.created_at)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Last Login'>
          {formatDateTime(user.last_auth_time)}
        </AdminReadOnlyValue>
        <AdminReadOnlyValue label='Managed organizations' span='full'>
          <ManagedOrganizations organizations={user.managed_organizations} />
        </AdminReadOnlyValue>
      </AdminFieldGrid>
    </AdminEditorPanel>
  );
}
