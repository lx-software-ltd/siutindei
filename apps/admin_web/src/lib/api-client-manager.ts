import type {
  Activity,
  ActivityPricing,
  ActivitySchedule,
  Location,
  Organization,
} from '../types/admin';
import type { ListResponse } from './api-client-core';
import { buildApiUrl, request } from './api-client-core';

function buildManagerUrl(resource: string, id?: string) {
  return id
    ? buildApiUrl(`v1/manager/${resource}/${id}`)
    : buildApiUrl(`v1/manager/${resource}`);
}

export async function listManagerOrganizations<
  T = Organization,
>(orgId?: string): Promise<ListResponse<T>> {
  const url = new URL(buildManagerUrl('organizations'));
  if (orgId) {
    url.searchParams.set('org_id', orgId);
  }
  return request<ListResponse<T>>(url.toString());
}

export async function getManagerOrganization(
  id: string
): Promise<Organization> {
  return request<Organization>(buildManagerUrl('organizations', id));
}

export async function updateManagerOrganization<
  TInput,
  TOutput = Organization,
>(
  id: string,
  payload: TInput
): Promise<TOutput> {
  return request<TOutput>(buildManagerUrl('organizations', id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteManagerOrganization(id: string): Promise<void> {
  return request<void>(buildManagerUrl('organizations', id), {
    method: 'DELETE',
  });
}

export async function listManagerLocations<
  T = Location,
>(orgId?: string): Promise<ListResponse<T>> {
  const url = new URL(buildManagerUrl('locations'));
  if (orgId) {
    url.searchParams.set('org_id', orgId);
  }
  return request<ListResponse<T>>(url.toString());
}

export async function getManagerLocation(id: string): Promise<Location> {
  return request<Location>(buildManagerUrl('locations', id));
}

export async function createManagerLocation<
  TInput,
  TOutput = Location,
>(
  payload: TInput
): Promise<TOutput> {
  return request<TOutput>(buildManagerUrl('locations'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updateManagerLocation<
  TInput,
  TOutput = Location,
>(
  id: string,
  payload: TInput
): Promise<TOutput> {
  return request<TOutput>(buildManagerUrl('locations', id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteManagerLocation(id: string): Promise<void> {
  return request<void>(buildManagerUrl('locations', id), {
    method: 'DELETE',
  });
}

export async function listManagerActivities<
  T = Activity,
>(orgId?: string): Promise<ListResponse<T>> {
  const url = new URL(buildManagerUrl('activities'));
  if (orgId) {
    url.searchParams.set('org_id', orgId);
  }
  return request<ListResponse<T>>(url.toString());
}

export async function getManagerActivity(id: string): Promise<Activity> {
  return request<Activity>(buildManagerUrl('activities', id));
}

export async function createManagerActivity<
  TInput,
  TOutput = Activity,
>(
  payload: TInput
): Promise<TOutput> {
  return request<TOutput>(buildManagerUrl('activities'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updateManagerActivity<
  TInput,
  TOutput = Activity,
>(
  id: string,
  payload: TInput
): Promise<TOutput> {
  return request<TOutput>(buildManagerUrl('activities', id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteManagerActivity(id: string): Promise<void> {
  return request<void>(buildManagerUrl('activities', id), {
    method: 'DELETE',
  });
}

export async function listManagerPricing<
  T = ActivityPricing,
>(orgId?: string): Promise<ListResponse<T>> {
  const url = new URL(buildManagerUrl('pricing'));
  if (orgId) {
    url.searchParams.set('org_id', orgId);
  }
  return request<ListResponse<T>>(url.toString());
}

export async function getManagerPricing(id: string): Promise<ActivityPricing> {
  return request<ActivityPricing>(buildManagerUrl('pricing', id));
}

export async function createManagerPricing<
  TInput,
  TOutput = ActivityPricing,
>(
  payload: TInput
): Promise<TOutput> {
  return request<TOutput>(buildManagerUrl('pricing'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updateManagerPricing<
  TInput,
  TOutput = ActivityPricing,
>(
  id: string,
  payload: TInput
): Promise<TOutput> {
  return request<TOutput>(buildManagerUrl('pricing', id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteManagerPricing(id: string): Promise<void> {
  return request<void>(buildManagerUrl('pricing', id), {
    method: 'DELETE',
  });
}

export async function listManagerSchedules<
  T = ActivitySchedule,
>(orgId?: string): Promise<ListResponse<T>> {
  const url = new URL(buildManagerUrl('schedules'));
  if (orgId) {
    url.searchParams.set('org_id', orgId);
  }
  return request<ListResponse<T>>(url.toString());
}

export async function getManagerSchedule(id: string): Promise<ActivitySchedule> {
  return request<ActivitySchedule>(buildManagerUrl('schedules', id));
}

export async function createManagerSchedule<
  TInput,
  TOutput = ActivitySchedule,
>(
  payload: TInput
): Promise<TOutput> {
  return request<TOutput>(buildManagerUrl('schedules'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updateManagerSchedule<
  TInput,
  TOutput = ActivitySchedule,
>(
  id: string,
  payload: TInput
): Promise<TOutput> {
  return request<TOutput>(buildManagerUrl('schedules', id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteManagerSchedule(id: string): Promise<void> {
  return request<void>(buildManagerUrl('schedules', id), {
    method: 'DELETE',
  });
}
