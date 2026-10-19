'use client';

import { useCallback, useEffect, useState } from 'react';

import {
  ApiError,
  listManagerOrganizations,
  listResource,
} from '../lib/api-client';
import type { ApiMode } from '../lib/resource-api';
import type { Organization } from '../types/admin';

interface UseOrganizationsByModeOptions {
  limit?: number;
  fetchAll?: boolean;
}

interface UseOrganizationsByModeResult {
  items: Organization[];
  isLoading: boolean;
  error: string;
  reload: () => void;
}

export function useOrganizationsByMode(
  mode: ApiMode,
  options: UseOrganizationsByModeOptions = {}
): UseOrganizationsByModeResult {
  const limit = options.limit;
  const fetchAll = options.fetchAll;
  const [reloadToken, setReloadToken] = useState(0);
  const requestKey = `${mode}:${limit ?? ''}:${fetchAll ? 'all' : 'page'}:${reloadToken}`;
  const [items, setItems] = useState<Organization[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [seenKey, setSeenKey] = useState(requestKey);

  if (seenKey !== requestKey) {
    setSeenKey(requestKey);
    setIsLoading(true);
    setError('');
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (mode === 'admin') {
          const pageSize = limit ?? 200;
          if (fetchAll) {
            const allItems: Organization[] = [];
            let cursor: string | undefined;
            do {
              const response = await listResource<Organization>(
                'organizations',
                cursor,
                pageSize
              );
              allItems.push(...response.items);
              cursor = response.next_cursor ?? undefined;
            } while (cursor);
            if (!cancelled) {
              setItems(allItems);
            }
          } else {
            const response = await listResource<Organization>(
              'organizations',
              undefined,
              pageSize
            );
            if (!cancelled) {
              setItems(response.items);
            }
          }
        } else {
          const response = await listManagerOrganizations();
          if (!cancelled) {
            setItems(response.items);
          }
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        const message =
          err instanceof ApiError
            ? err.message
            : 'Failed to load organizations.';
        setError(message);
        setItems([]);
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, fetchAll, limit, reloadToken]);

  const reload = useCallback(() => {
    setReloadToken((current) => current + 1);
  }, []);

  return {
    items,
    isLoading,
    error,
    reload,
  };
}
