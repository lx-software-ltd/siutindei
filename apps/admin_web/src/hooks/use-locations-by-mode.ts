'use client';

import { useCallback, useEffect, useState } from 'react';

import {
  ApiError,
  listManagerLocations,
  listResource,
} from '../lib/api-client';
import type { ApiMode } from '../lib/resource-api';
import type { Location } from '../types/admin';

interface UseLocationsByModeOptions {
  limit?: number;
  /** `null` skips the request until a workspace organization is chosen. */
  orgId?: string | null;
}

interface UseLocationsByModeResult {
  items: Location[];
  isLoading: boolean;
  error: string;
  reload: () => void;
}

export function useLocationsByMode(
  mode: ApiMode,
  options: UseLocationsByModeOptions = {}
): UseLocationsByModeResult {
  const [items, setItems] = useState<Location[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const orgId = options.orgId;
  const loadLocations = useCallback(async () => {
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
        const response = await listResource<Location>(
          'locations',
          undefined,
          limit,
          undefined,
          orgId ? { org_id: orgId } : undefined
        );
        setItems(response.items);
      } else {
        const response = await listManagerLocations(orgId ?? undefined);
        setItems(response.items);
      }
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'Failed to load locations.';
      setError(message);
      setItems([]);
    } finally {
      setIsLoading(false);
    }
  }, [mode, options.limit, orgId]);

  useEffect(() => {
    loadLocations();
  }, [loadLocations]);

  return {
    items,
    isLoading,
    error,
    reload: loadLocations,
  };
}
