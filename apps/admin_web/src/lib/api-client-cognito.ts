import type { CognitoUser } from '../types/admin';
import { buildApiUrl, request } from './api-client-core';

export interface CognitoUsersResponse {
  items: CognitoUser[];
  pagination_token?: string | null;
}

export interface UserGroupResponse {
  message: string;
  username: string;
  group_name: string;
}

export interface DeleteCognitoUserResponse {
  message: string;
  username: string;
  fallback_manager_id: string;
  transferred_organizations_count: number;
}

function buildCognitoUsersUrl() {
  return buildApiUrl('v1/admin/cognito-users');
}

function buildUserGroupsUrl(username: string) {
  return buildApiUrl(`v1/admin/cognito-users/groups/${username}`);
}

export async function createCognitoManager(
  email: string
): Promise<CognitoUser> {
  return request<CognitoUser>(buildCognitoUsersUrl(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email }),
  });
}

export async function listCognitoUsers(
  paginationToken?: string,
  limit = 50,
  query?: string,
  include?: 'managed_organizations'
): Promise<CognitoUsersResponse> {
  const url = new URL(buildCognitoUsersUrl());
  url.searchParams.set('limit', `${limit}`);
  if (paginationToken) {
    url.searchParams.set('pagination_token', paginationToken);
  }
  if (query?.trim()) {
    url.searchParams.set('q', query.trim());
  }
  if (include) {
    url.searchParams.set('include', include);
  }
  return request<CognitoUsersResponse>(url.toString());
}

export async function addUserToGroup(
  username: string,
  groupName: 'admin' | 'manager'
): Promise<UserGroupResponse> {
  return request<UserGroupResponse>(buildUserGroupsUrl(username), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ group_name: groupName }),
  });
}

export async function removeUserFromGroup(
  username: string,
  groupName: 'admin' | 'manager'
): Promise<UserGroupResponse> {
  return request<UserGroupResponse>(buildUserGroupsUrl(username), {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ group_name: groupName }),
  });
}

export async function deleteCognitoUser(
  username: string
): Promise<DeleteCognitoUserResponse> {
  return request<DeleteCognitoUserResponse>(
    buildApiUrl(`v1/admin/cognito-users/${username}`),
    {
      method: 'DELETE',
    }
  );
}
