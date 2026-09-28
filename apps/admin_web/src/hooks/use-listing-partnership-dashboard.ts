'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  ApiError,
  listApiKeys,
  listResource,
  listTickets,
} from '../lib/api-client';
import {
  buildListingPartnershipMetrics,
  buildRecentUpdates,
  type DashboardRecentUpdate,
  type ListingPartnershipMetrics,
} from '../lib/listing-partnership-dashboard';
import type { ApiKey, Organization } from '../types/admin';
import type { Ticket } from '../lib/api-client-tickets';

interface UseListingPartnershipDashboardResult {
  metrics: ListingPartnershipMetrics | null;
  recentUpdates: DashboardRecentUpdate[];
  isLoading: boolean;
  error: string;
  reload: () => void;
}

async function fetchAllOrganizations(): Promise<Organization[]> {
  const allItems: Organization[] = [];
  let cursor: string | undefined;
  const limit = 200;
  do {
    const response = await listResource<Organization>(
      'organizations',
      cursor,
      limit
    );
    allItems.push(...response.items);
    cursor = response.next_cursor ?? undefined;
  } while (cursor);
  return allItems;
}

async function fetchAllApiKeys(): Promise<ApiKey[]> {
  const allItems: ApiKey[] = [];
  let cursor: string | undefined;
  const limit = 100;
  do {
    const response = await listApiKeys(cursor, limit);
    allItems.push(...response.items);
    cursor = response.next_cursor ?? undefined;
  } while (cursor);
  return allItems;
}

async function fetchAllPendingTickets(): Promise<Ticket[]> {
  const allItems: Ticket[] = [];
  let cursor: string | undefined;
  const limit = 100;
  do {
    const response = await listTickets(undefined, 'pending', cursor);
    allItems.push(...response.items);
    cursor = response.next_cursor ?? undefined;
  } while (cursor);
  return allItems;
}

export function useListingPartnershipDashboard(): UseListingPartnershipDashboardResult {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [pendingTickets, setPendingTickets] = useState<Ticket[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const [orgs, tickets, keys] = await Promise.all([
        fetchAllOrganizations(),
        fetchAllPendingTickets(),
        fetchAllApiKeys(),
      ]);
      setOrganizations(orgs);
      setPendingTickets(tickets);
      setApiKeys(keys);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Failed to load listing and partnership metrics.';
      setError(message);
      setOrganizations([]);
      setPendingTickets([]);
      setApiKeys([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const metrics = useMemo(() => {
    if (isLoading && organizations.length === 0 && !error) {
      return null;
    }
    return buildListingPartnershipMetrics(
      organizations,
      pendingTickets,
      apiKeys
    );
  }, [apiKeys, error, isLoading, organizations, pendingTickets]);

  const recentUpdates = useMemo(
    () => buildRecentUpdates(organizations, pendingTickets),
    [organizations, pendingTickets]
  );

  return {
    metrics,
    recentUpdates,
    isLoading,
    error,
    reload: load,
  };
}
