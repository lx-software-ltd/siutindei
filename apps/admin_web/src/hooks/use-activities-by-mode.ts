'use client';

import { useCallback, useEffect, useState } from 'react';

import {
  ApiError,
  listManagerActivities,
  listResource,
} from '../lib/api-client';
import type { ApiMode } from '../lib/resource-api';
import type { Activity } from '../types/admin';

interface UseActivitiesByModeOptions {
  limit?: number;
  /** `null` skips the request until a workspace organization is chosen. */
  orgId?: string | null;
}

interface UseActivitiesByModeResult {
  items: Activity[];
  isLoading: boolean;
  error: string;
  reload: () => void;
}

export function useActivitiesByMode(
  mode: ApiMode,
  options: UseActivitiesByModeOptions = {}
): UseActivitiesByModeResult {
  const orgId = options.orgId;
  const limit = options.limit;
  const skipped = orgId === null;
  const [reloadToken, setReloadToken] = useState(0);
  const requestKey = skipped
    ? 'skip'
    : `${mode}:${limit ?? ''}:${orgId ?? ''}:${reloadToken}`;
  const [items, setItems] = useState<Activity[]>([]);
  const [isLoading, setIsLoading] = useState(!skipped);
  const [error, setError] = useState('');
  const [seenKey, setSeenKey] = useState(requestKey);

  if (seenKey !== requestKey) {
    setSeenKey(requestKey);
    setError('');
    if (skipped) {
      setItems([]);
      setIsLoading(false);
    } else {
      setIsLoading(true);
    }
  }

  useEffect(() => {
    if (skipped) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        if (mode === 'admin') {
          const response = await listResource<Activity>(
            'activities',
            undefined,
            limit ?? 200,
            undefined,
            orgId ? { org_id: orgId } : undefined
          );
          if (!cancelled) {
            setItems(response.items);
          }
        } else {
          const response = await listManagerActivities(orgId ?? undefined);
          if (!cancelled) {
            setItems(response.items);
          }
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        const message =
          err instanceof ApiError ? err.message : 'Failed to load activities.';
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
  }, [skipped, mode, limit, orgId, reloadToken]);

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
