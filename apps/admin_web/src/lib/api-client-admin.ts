import { ADMIN_LIST_PAGE_SIZE } from './admin-list-query';
import type { ListResponse } from './api-client-core';
import { buildApiUrl, request } from './api-client-core';

export type ApiBasePath = 'v1/admin' | 'v1/manager';

export type ApiMode = 'admin' | 'manager';

export type ResourceName =
  | 'organizations'
  | 'locations'
  | 'activity-categories'
  | 'activities'
  | 'pricing'
  | 'schedules'
  | 'feedback-labels'
  | 'organization-feedback';

export type ResourceType = ResourceName;

export interface ResourceListFilters {
  org_id?: string;
  [key: string]: string | undefined;
}

export interface ResourceApi<T> {
  list: (
    cursor?: string,
    limit?: number,
    signal?: AbortSignal,
    filters?: ResourceListFilters
  ) => Promise<ListResponse<T>>;
  get: (id: string, signal?: AbortSignal) => Promise<T>;
  create?: <TInput>(payload: TInput) => Promise<T>;
  update: <TInput>(id: string, payload: TInput) => Promise<T>;
  delete: (id: string) => Promise<void>;
}

const MANAGER_RESOURCES = new Set<ResourceName>([
  'organizations',
  'locations',
  'activities',
  'pricing',
  'schedules',
]);

function buildResourceUrl(basePath: ApiBasePath, resource: ResourceName, id?: string) {
  return id
    ? buildApiUrl(`${basePath}/${resource}/${id}`)
    : buildApiUrl(`${basePath}/${resource}`);
}

function managerListFilters(filters?: ResourceListFilters) {
  return filters?.org_id ? { org_id: filters.org_id } : undefined;
}

export async function getResource<T>(
  basePath: ApiBasePath,
  resource: ResourceName,
  id: string,
  signal?: AbortSignal
): Promise<T> {
  return request<T>(buildResourceUrl(basePath, resource, id), { signal });
}

export async function listResource<T>(
  basePath: ApiBasePath,
  resource: ResourceName,
  cursor?: string,
  limit?: number,
  signal?: AbortSignal,
  filters?: Record<string, string | undefined>
): Promise<ListResponse<T>> {
  const url = new URL(buildResourceUrl(basePath, resource));
  if (cursor) {
    url.searchParams.set('cursor', cursor);
  }
  const pageSize = limit ?? (basePath === 'v1/admin' ? ADMIN_LIST_PAGE_SIZE : undefined);
  if (pageSize !== undefined) {
    url.searchParams.set('limit', `${pageSize}`);
  }
  for (const [key, value] of Object.entries(filters ?? {})) {
    if (value) {
      url.searchParams.set(key, value);
    }
  }
  return request<ListResponse<T>>(url.toString(), { signal });
}

export async function createResource<TInput, TOutput>(
  basePath: ApiBasePath,
  resource: ResourceName,
  payload: TInput
) {
  return request<TOutput>(buildResourceUrl(basePath, resource), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updateResource<TInput, TOutput>(
  basePath: ApiBasePath,
  resource: ResourceName,
  id: string,
  payload: TInput
) {
  return request<TOutput>(buildResourceUrl(basePath, resource, id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteResource(basePath: ApiBasePath, resource: ResourceName, id: string) {
  return request<void>(buildResourceUrl(basePath, resource, id), {
    method: 'DELETE',
  });
}

function managerResourceApi<T>(resource: ResourceName, allowCreate: boolean): ResourceApi<T> {
  const api: ResourceApi<T> = {
    list: (_cursor, _limit, _signal, filters) =>
      listResource<T>(
        'v1/manager',
        resource,
        undefined,
        undefined,
        undefined,
        managerListFilters(filters)
      ),
    get: (id: string) => getResource<T>('v1/manager', resource, id),
    update: <TInput>(id: string, payload: TInput) =>
      updateResource<TInput, T>('v1/manager', resource, id, payload),
    delete: (id: string) => deleteResource('v1/manager', resource, id),
  };
  if (allowCreate) {
    api.create = <TInput>(payload: TInput) =>
      createResource<TInput, T>('v1/manager', resource, payload);
  }
  return api;
}

/**
 * Resource CRUD for admin (`v1/admin`) or manager (`v1/manager`).
 * Manager lists send only `org_id` and omit cursor, limit, and abort.
 * Managers cannot create organizations. Other manager resources throw.
 */
export function getResourceApi<T>(resource: ResourceType, mode: ApiMode): ResourceApi<T> {
  if (mode === 'admin') {
    return {
      list: (cursor, limit, signal, filters) =>
        listResource<T>('v1/admin', resource, cursor, limit, signal, filters),
      get: (id: string, signal?: AbortSignal) => getResource<T>('v1/admin', resource, id, signal),
      create: <TInput>(payload: TInput) => createResource<TInput, T>('v1/admin', resource, payload),
      update: <TInput>(id: string, payload: TInput) =>
        updateResource<TInput, T>('v1/admin', resource, id, payload),
      delete: (id: string) => deleteResource('v1/admin', resource, id),
    };
  }
  if (!MANAGER_RESOURCES.has(resource)) {
    throw new Error(`Unknown resource type: ${resource}`);
  }
  return managerResourceApi<T>(resource, resource !== 'organizations');
}
