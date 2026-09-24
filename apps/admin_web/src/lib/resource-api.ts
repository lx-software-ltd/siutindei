/**
 * Unified resource API helpers for both admin and manager modes.
 *
 * Admin mode: Full access to all resources via /v1/admin/*
 * Manager mode: Filtered access to managed resources via /v1/manager/*
 */

import {
  ApiError,
  createResource,
  deleteResource,
  listResource,
  updateResource,
  listManagerOrganizations,
  createManagerLocation,
  createManagerActivity,
  createManagerPricing,
  createManagerSchedule,
  listManagerLocations,
  listManagerActivities,
  listManagerPricing,
  listManagerSchedules,
  updateManagerOrganization,
  updateManagerLocation,
  updateManagerActivity,
  updateManagerPricing,
  updateManagerSchedule,
  deleteManagerOrganization,
  deleteManagerLocation,
  deleteManagerActivity,
  deleteManagerPricing,
  deleteManagerSchedule,
  type ListResponse,
} from './api-client';

export type ApiMode = 'admin' | 'manager';

export type ResourceType =
  | 'organizations'
  | 'locations'
  | 'activity-categories'
  | 'activities'
  | 'pricing'
  | 'schedules'
  | 'feedback-labels'
  | 'organization-feedback';

export interface ResourceApi<T> {
  list: (
    cursor?: string,
    limit?: number,
    signal?: AbortSignal
  ) => Promise<ListResponse<T>>;
  create?: <TInput>(payload: TInput) => Promise<T>;
  update: <TInput>(id: string, payload: TInput) => Promise<T>;
  delete: (id: string) => Promise<void>;
}

/**
 * Get the appropriate API functions for a resource based on mode.
 */
export function getResourceApi<T>(
  resource: ResourceType,
  mode: ApiMode
): ResourceApi<T> {
  if (mode === 'admin') {
    return {
      list: (cursor?: string, limit?: number, signal?: AbortSignal) =>
        listResource<T>(resource, cursor, limit, signal),
      create: <TInput>(payload: TInput) =>
        createResource<TInput, T>(resource, payload),
      update: <TInput>(id: string, payload: TInput) =>
        updateResource<TInput, T>(resource, id, payload),
      delete: (id: string) => deleteResource(resource, id),
    };
  }

  // Manager mode - use manager-specific endpoints
  switch (resource) {
    case 'organizations':
      return {
        list: () => listManagerOrganizations<T>(),
        // Managers cannot create organizations
        update: <TInput>(id: string, payload: TInput) =>
          updateManagerOrganization<TInput, T>(id, payload),
        delete: (id: string) => deleteManagerOrganization(id),
      };
    case 'locations':
      return {
        list: () => listManagerLocations<T>(),
        create: <TInput>(payload: TInput) =>
          createManagerLocation<TInput, T>(payload),
        update: <TInput>(id: string, payload: TInput) =>
          updateManagerLocation<TInput, T>(id, payload),
        delete: (id: string) => deleteManagerLocation(id),
      };
    case 'activities':
      return {
        list: () => listManagerActivities<T>(),
        create: <TInput>(payload: TInput) =>
          createManagerActivity<TInput, T>(payload),
        update: <TInput>(id: string, payload: TInput) =>
          updateManagerActivity<TInput, T>(id, payload),
        delete: (id: string) => deleteManagerActivity(id),
      };
    case 'pricing':
      return {
        list: () => listManagerPricing<T>(),
        create: <TInput>(payload: TInput) =>
          createManagerPricing<TInput, T>(payload),
        update: <TInput>(id: string, payload: TInput) =>
          updateManagerPricing<TInput, T>(id, payload),
        delete: (id: string) => deleteManagerPricing(id),
      };
    case 'schedules':
      return {
        list: () => listManagerSchedules<T>(),
        create: <TInput>(payload: TInput) =>
          createManagerSchedule<TInput, T>(payload),
        update: <TInput>(id: string, payload: TInput) =>
          updateManagerSchedule<TInput, T>(id, payload),
        delete: (id: string) => deleteManagerSchedule(id),
      };
    default:
      throw new Error(`Unknown resource type: ${resource}`);
  }
}

export { ApiError };
