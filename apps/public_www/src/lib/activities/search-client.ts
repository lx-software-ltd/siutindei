import { fetchStagingActivitySearch } from '@/lib/activities/staging-search';
import { getSearchConfig } from '@/lib/site-config';

import type {
  ActivityListing,
  ActivitySearchParams,
  ActivitySearchResponse,
  TranslationMap,
} from './types';

function mapTranslationMap(value: Record<string, string> | undefined): TranslationMap {
  return value ?? {};
}

function mapListing(item: {
  activity: {
    id: string;
    name: string;
    description: string | null;
    name_translations?: Record<string, string>;
    description_translations?: Record<string, string>;
    age_min?: number | null;
    age_max?: number | null;
    category_id?: string | null;
  };
  organization: {
    id: string;
    name: string;
    description?: string | null;
    name_translations?: Record<string, string>;
    media_urls?: string[];
    logo_media_url?: string | null;
    status?: string | null;
    description_source?: string | null;
    place_id?: string | null;
  };
  location: {
    id: string;
    area_id: string;
    region_area_id?: string | null;
    address?: string | null;
    lat?: number | null;
    lng?: number | null;
  };
  pricing: {
    pricing_type: string;
    amount: number;
    currency: string;
    sessions_count?: number | null;
    free_trial_class_offered: boolean;
  };
  schedule: {
    schedule_type: string;
    weekly_entries: Array<{
      day_of_week_utc: number;
      start_minutes_utc: number;
      end_minutes_utc: number;
    }>;
    languages: string[];
  };
}): ActivityListing {
  return {
    activity: {
      id: item.activity.id,
      name: item.activity.name,
      description: item.activity.description,
      nameTranslations: mapTranslationMap(item.activity.name_translations),
      descriptionTranslations: mapTranslationMap(
        item.activity.description_translations,
      ),
      ageMin: item.activity.age_min ?? null,
      ageMax: item.activity.age_max ?? null,
      categoryId: item.activity.category_id ?? null,
    },
    organization: {
      id: item.organization.id,
      name: item.organization.name,
      description: item.organization.description ?? null,
      nameTranslations: mapTranslationMap(item.organization.name_translations),
      mediaUrls: item.organization.media_urls ?? [],
      logoMediaUrl: item.organization.logo_media_url ?? null,
      status: item.organization.status ?? null,
      descriptionSource: item.organization.description_source ?? null,
      placeId: item.organization.place_id ?? null,
    },
    location: {
      id: item.location.id,
      areaId: item.location.area_id,
      regionAreaId: item.location.region_area_id ?? null,
      address: item.location.address ?? null,
      lat: item.location.lat ?? null,
      lng: item.location.lng ?? null,
    },
    pricing: {
      pricingType: item.pricing.pricing_type,
      amount: item.pricing.amount,
      currency: item.pricing.currency,
      sessionsCount: item.pricing.sessions_count ?? null,
      freeTrialClassOffered: item.pricing.free_trial_class_offered,
    },
    schedule: {
      scheduleType: item.schedule.schedule_type,
      weeklyEntries: (item.schedule.weekly_entries ?? []).map((entry) => ({
        dayOfWeekUtc: entry.day_of_week_utc,
        startMinutesUtc: entry.start_minutes_utc,
        endMinutesUtc: entry.end_minutes_utc,
      })),
      languages: item.schedule.languages ?? [],
    },
  };
}

interface FetchActivitySearchOptions {
  readonly highPriority?: boolean;
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
    ...(options?.highPriority ? { priority: 'high' as RequestPriority } : {}),
  });
  if (!response.ok) {
    throw new Error(`Search failed with status ${response.status}`);
  }

  const payload = (await response.json()) as {
    items?: unknown[];
    next_cursor?: string | null;
  };

  const items = (payload.items ?? []).map((item) =>
    mapListing(item as Parameters<typeof mapListing>[0]),
  );

  return {
    items,
    nextCursor: payload.next_cursor ?? null,
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
