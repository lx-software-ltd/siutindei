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
  const [items, setItems] = useState<Activity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const orgId = options.orgId;
  const loadActivities = useCallback(async () => {
    if (orgId === null) {
      setItems([]);
      setError('');
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError('');
    try {
      if (mode === 'admin') {
        const limit = options.limit ?? 200;
        const response = await listResource<Activity>(
          'activities',
          undefined,
          limit,
          undefined,
          orgId ? { org_id: orgId } : undefined
        );
        setItems(response.items);
      } else {
        const response = await listManagerActivities(orgId ?? undefined);
        setItems(response.items);
      }
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'Failed to load activities.';
      setError(message);
      setItems([]);
    } finally {
      setIsLoading(false);
    }
  }, [mode, options.limit, orgId]);

  useEffect(() => {
    loadActivities();
  }, [loadActivities]);

  return {
    items,
    isLoading,
    error,
    reload: loadActivities,
  };
}
