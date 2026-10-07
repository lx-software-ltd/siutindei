'use client';

import { useCallback } from 'react';

import { ADMIN_LIST_PAGE_SIZE } from '@/lib/admin-list-query';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import {
  getResourceApi,
  type ResourceListFilters,
  type ResourceType,
} from '@/lib/resource-api';

import { prefetchPaginatedList } from './use-paginated-list';

const SCOPED_RESOURCES = new Set<ResourceType>([
  'locations',
  'activities',
  'pricing',
  'schedules',
]);

const PREFETCH_RESOURCES: Record<string, ResourceType> = {
  organizations: 'organizations',
  locations: 'locations',
  activities: 'activities',
  pricing: 'pricing',
  schedules: 'schedules',
  'activity-categories': 'activity-categories',
  'feedback-labels': 'feedback-labels',
  feedback: 'organization-feedback',
};

/** Warm the first page of a section list on nav hover or focus. */
export function usePrefetchAdminSection(
  mode: 'admin' | 'manager' = 'admin',
  orgId?: string | null
) {
  return useCallback(
    (sectionKey: string) => {
      const resource = PREFETCH_RESOURCES[sectionKey];
      if (!resource) {
        return;
      }
      const scoped = SCOPED_RESOURCES.has(resource);
      if (scoped && !orgId) {
        return;
      }
      const listFilters: ResourceListFilters =
        scoped && orgId ? { org_id: orgId } : {};
      let api: ReturnType<typeof getResourceApi>;
      try {
        api = getResourceApi(resource, mode);
      } catch {
        // Manager mode has no API for some admin resources (feedback).
        return;
      }
      void prefetchPaginatedList({
        queryKey: [
          ...adminQueryKeys.resourceList(resource, mode),
          JSON.stringify(listFilters),
        ],
        filters: {},
        limit: ADMIN_LIST_PAGE_SIZE,
        fetcher: async ({ cursor, limit, signal }) => {
          const response = await api.list(
            cursor ?? undefined,
            limit,
            signal,
            listFilters
          );
          return {
            items: response.items,
            nextCursor: response.next_cursor ?? null,
          };
        },
      });
    },
    [mode, orgId]
  );
}
