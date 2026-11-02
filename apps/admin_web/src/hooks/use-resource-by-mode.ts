'use client';

import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { getAdminQueryClient } from '@/lib/admin-query-client';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import { ApiError } from '@/lib/api-client-core';
import {
  listResource,
  type ApiMode,
  type ResourceName,
} from '@/lib/api-client-admin';

interface UseResourceByModeOptions {
  limit?: number;
  /** `null` skips the request until a workspace organization is chosen. */
  orgId?: string | null;
  /** Follow admin cursors until they run out. Manager lists are a single page. */
  fetchAll?: boolean;
}

const DEFAULT_LIMIT = 200;

function loadError(resource: ResourceName, error: unknown): string {
  if (!error) {
    return '';
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  return `Failed to load ${resource}.`;
}

/**
 * One list for admin and manager modes. `orgId: null` waits for a workspace.
 * Admin requests use cursor and limit. Manager requests send only `org_id`.
 */
export function useResourceByMode<T>(
  resource: ResourceName,
  mode: ApiMode,
  options: UseResourceByModeOptions = {}
) {
  const orgId = options.orgId;
  const limit = options.limit ?? DEFAULT_LIMIT;
  const fetchAll = options.fetchAll ?? false;
  const skipped = orgId === null;
  const filters = orgId ? { org_id: orgId } : undefined;

  const query = useQuery(
    {
      queryKey: [
        ...adminQueryKeys.resourceList(resource, mode),
        'by-mode',
        limit,
        orgId ?? null,
        fetchAll,
      ],
      enabled: !skipped,
      placeholderData: keepPreviousData,
      queryFn: async ({ signal }) => {
        if (mode === 'manager') {
          const response = await listResource<T>(
            'v1/manager',
            resource,
            undefined,
            undefined,
            undefined,
            filters
          );
          return response.items;
        }
        if (!fetchAll) {
          const response = await listResource<T>(
            'v1/admin',
            resource,
            undefined,
            limit,
            signal,
            filters
          );
          return response.items;
        }
        const items: T[] = [];
        let cursor: string | undefined;
        do {
          const response = await listResource<T>(
            'v1/admin',
            resource,
            cursor,
            limit,
            signal,
            filters
          );
          items.push(...response.items);
          cursor = response.next_cursor ?? undefined;
        } while (cursor);
        return items;
      },
    },
    getAdminQueryClient()
  );

  return {
    items: skipped ? [] : (query.data ?? []),
    isLoading: skipped ? false : query.isLoading || (query.isFetching && query.isPlaceholderData),
    error: skipped ? '' : loadError(resource, query.error),
    reload: () => {
      void query.refetch();
    },
  };
}
