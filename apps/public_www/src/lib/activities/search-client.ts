import { fetchStagingActivitySearch } from '@/lib/activities/staging-search';
import { getSearchConfig } from '@/lib/site-config';

import { groupListings } from './group-listings';
import { mapActivityListing, type ActivityWireListing } from './map-listing';
import { ACTIVITY_DETAIL_PAGE_LIMIT } from './search-limits';
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
  if (params.kinds && params.kinds.length > 0) {
    url.searchParams.set('kind', params.kinds.join(','));
  }
  if (params.ageMin !== undefined) {
    url.searchParams.set('age_min', String(params.ageMin));
  }
  if (params.ageMax !== undefined) {
    url.searchParams.set('age_max', String(params.ageMax));
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
  url.searchParams.set('include_incomplete', 'true');
  for (const categoryId of params.categoryIds ?? []) {
    url.searchParams.append('category_id', categoryId);
  }
  for (const organizationId of params.organizationIds ?? []) {
    url.searchParams.append('organization_id', organizationId);
  }
  if (params.pricingType) {
    url.searchParams.set('pricing_type', params.pricingType);
  }
  for (const language of params.languages ?? []) {
    url.searchParams.append('language', language);
  }
  for (const day of params.daysOfWeekHkt ?? []) {
    url.searchParams.append('day_of_week_hkt', String(day));
  }
  if (params.freeTrial) {
    url.searchParams.set('free_trial', 'true');
  }
  if (params.classPriceMax !== undefined) {
    url.searchParams.set('class_price_max', String(params.classPriceMax));
  }
  if (params.sort && params.sort !== 'time') {
    url.searchParams.set('sort', params.sort);
  }
  if (params.includeTotal && !params.cursor) {
    url.searchParams.set('include_total', 'true');
  }
  const sortedEntries = [...url.searchParams.entries()].sort((left, right) => {
    if (left[0] === right[0]) {
      if (left[1] === right[1]) {
        return 0;
      }
      return left[1] < right[1] ? -1 : 1;
    }
    return left[0] < right[0] ? -1 : 1;
  });
  url.search = '';
  for (const [key, value] of sortedEntries) {
    url.searchParams.append(key, value);
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
    total?: number | null;
  };

  const items = (payload.items ?? []).map((item) =>
    mapActivityListing(item as ActivityWireListing, params.view ?? 'full'),
  );

  return {
    items,
    nextCursor: payload.next_cursor ?? null,
    categoryMatch: payload.category_match ?? 'exact',
    total: payload.total ?? null,
  };
}

const DETAIL_MAX_PAGES = 4;

/** Every venue, price, and schedule row of one activity, grouped. */
export async function fetchActivityListingById(
  activityId: string,
): Promise<ActivityListing | null> {
  const rows: ActivityListing[] = [];
  let cursor: string | undefined;
  for (let page = 0; page < DETAIL_MAX_PAGES; page += 1) {
    const response = await fetchActivitySearch(
      {
        activityId,
        limit: ACTIVITY_DETAIL_PAGE_LIMIT,
        ...(cursor ? { cursor } : {}),
      },
      { highPriority: page === 0 },
    );
    rows.push(...response.items);
    if (!response.nextCursor) {
      break;
    }
    cursor = response.nextCursor;
  }
  return groupListings(rows)[0] ?? null;
}
