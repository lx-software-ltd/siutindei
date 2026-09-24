'use client';

import { useCallback } from 'react';

import { ADMIN_LIST_PAGE_SIZE } from '@/lib/admin-list-query';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import { getResourceApi, type ResourceType } from '@/lib/resource-api';

import { prefetchPaginatedList } from './use-paginated-list';

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
export function usePrefetchAdminSection(mode: 'admin' | 'manager' = 'admin') {
  return useCallback(
    (sectionKey: string) => {
      const resource = PREFETCH_RESOURCES[sectionKey];
      if (!resource) {
        return;
      }
      const api = getResourceApi(resource, mode);
      void prefetchPaginatedList({
        queryKey: adminQueryKeys.resourceList(resource, mode),
        filters: {},
        limit: ADMIN_LIST_PAGE_SIZE,
        fetcher: async ({ cursor, limit, signal }) => {
          const response = await api.list(cursor ?? undefined, limit, signal);
          return {
            items: response.items,
            nextCursor: response.next_cursor ?? null,
          };
        },
      });
    },
    [mode]
  );
}
