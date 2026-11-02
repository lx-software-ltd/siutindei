import { fetchStagingActivitySearch } from '@/lib/activities/staging-search';
import { getSearchConfig } from '@/lib/site-config';

import { mapActivityListing, type ActivityWireListing } from './map-listing';
import type {
  ActivityListing,
  ActivitySearchParams,
  ActivitySearchResponse,
} from './types';

interface FetchActivitySearchOptions {
  readonly highPriority?: boolean;
  readonly signal?: AbortSignal;
}

export interface ActivitySearchRequest {
  readonly url: string;
  readonly headers: Record<string, string>;
}

export function buildActivitySearchRequest(
  params: ActivitySearchParams,
  config: Pick<
    ReturnType<typeof getSearchConfig>,
    'apiBaseUrl' | 'apiKey' | 'attestationToken'
  >,
): ActivitySearchRequest {
  const url = new URL('/v1/activities/search', config.apiBaseUrl);
  if (params.age !== undefined) {
    url.searchParams.set('age', String(params.age));
  }
  if (params.areaId) {
    url.searchParams.set('area_id', params.areaId);
  }
  if (params.activityId) {
    url.searchParams.set('activity_id', params.activityId);
  }
  if (params.cursor) {
    url.searchParams.set('cursor', params.cursor);
  }
  url.searchParams.set('limit', String(params.limit ?? 50));
  if (params.q) {
    url.searchParams.set('q', params.q);
  }
  if (params.view) {
    url.searchParams.set('view', params.view);
  }
  for (const categoryId of params.categoryIds ?? []) {
    url.searchParams.append('category_id', categoryId);
  }

  const headers: Record<string, string> = {
    Accept: 'application/json',
  };
  if (config.apiKey) {
    headers['x-api-key'] = config.apiKey;
  }
  if (config.attestationToken) {
    headers['x-device-attestation'] = config.attestationToken;
  }

  return { url: url.toString(), headers };
}

export async function fetchActivitySearch(
  params: ActivitySearchParams,
  options?: FetchActivitySearchOptions,
): Promise<ActivitySearchResponse> {
  const config = getSearchConfig();
  if (config.stagingSearchDataEnabled) {
    return await fetchStagingActivitySearch(params);
  }
  if (!config.apiBaseUrl) {
    throw new Error('Search API is not configured.');
  }

  const { url, headers } = buildActivitySearchRequest(params, config);

  const response = await fetch(url, {
    headers,
    signal: options?.signal,
    ...(options?.highPriority ? { priority: 'high' as RequestPriority } : {}),
  });
  if (!response.ok) {
    throw new Error(`Search failed with status ${response.status}`);
  }

  const payload = (await response.json()) as {
    items?: unknown[];
    next_cursor?: string | null;
    category_match?: 'exact' | 'legacy_fallback';
  };

  const items = (payload.items ?? []).map((item) =>
    mapActivityListing(item as ActivityWireListing, params.view ?? 'full'),
  );

  return {
    items,
    nextCursor: payload.next_cursor ?? null,
    categoryMatch: payload.category_match ?? 'exact',
  };
}

export async function fetchActivityListingById(
  activityId: string,
): Promise<ActivityListing | null> {
  const response = await fetchActivitySearch(
    {
      activityId,
      limit: 1,
    },
    { highPriority: true },
  );
  return response.items[0] ?? null;
}
