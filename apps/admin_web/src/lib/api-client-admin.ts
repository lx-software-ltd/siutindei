import { ADMIN_LIST_PAGE_SIZE } from './admin-list-query';
import type { ListResponse } from './api-client-core';
import { buildApiUrl, request } from './api-client-core';

export type ResourceName =
  | 'organizations'
  | 'locations'
  | 'activity-categories'
  | 'activities'
  | 'pricing'
  | 'schedules'
  | 'feedback-labels'
  | 'organization-feedback';

function buildResourceUrl(resource: ResourceName, id?: string) {
  return id
    ? buildApiUrl(`v1/admin/${resource}/${id}`)
    : buildApiUrl(`v1/admin/${resource}`);
}

export async function getResource<T>(
  resource: ResourceName,
  id: string,
  signal?: AbortSignal
): Promise<T> {
  return request<T>(buildResourceUrl(resource, id), { signal });
}

export async function listResource<T>(
  resource: ResourceName,
  cursor?: string,
  limit = ADMIN_LIST_PAGE_SIZE,
  signal?: AbortSignal
): Promise<ListResponse<T>> {
  const url = new URL(buildResourceUrl(resource));
  if (cursor) {
    url.searchParams.set('cursor', cursor);
  }
  url.searchParams.set('limit', `${limit}`);
  return request<ListResponse<T>>(url.toString(), { signal });
}

export async function createResource<TInput, TOutput>(
  resource: ResourceName,
  payload: TInput
) {
  return request<TOutput>(buildResourceUrl(resource), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updateResource<TInput, TOutput>(
  resource: ResourceName,
  id: string,
  payload: TInput
) {
  return request<TOutput>(buildResourceUrl(resource, id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteResource(resource: ResourceName, id: string) {
  return request<void>(buildResourceUrl(resource, id), {
    method: 'DELETE',
  });
}
