import { getSearchConfig, getSiteConfig } from '@/lib/site-config';

import type {
  ActivityListing,
  ActivitySearchParams,
  ActivitySearchResponse,
} from './types';

interface StagingSortMeta {
  readonly day_of_week_utc: number;
  readonly start_minutes_utc: number;
  readonly schedule_id: string;
}

interface StagingFixtureItem {
  readonly activity: {
    readonly id: string;
    readonly name: string;
    readonly description: string | null;
    readonly name_translations?: Record<string, string>;
    readonly description_translations?: Record<string, string>;
    readonly age_min?: number | null;
    readonly age_max?: number | null;
    readonly category_id?: string | null;
  };
  readonly organization: {
    readonly id: string;
    readonly name: string;
    readonly description?: string | null;
    readonly name_translations?: Record<string, string>;
    readonly media_urls?: string[];
    readonly logo_media_url?: string | null;
    readonly status?: string | null;
    readonly description_source?: string | null;
    readonly place_id?: string | null;
  };
  readonly location: {
    readonly id: string;
    readonly area_id: string;
    readonly region_area_id?: string | null;
    readonly address?: string | null;
    readonly lat?: string | null;
    readonly lng?: string | null;
  };
  readonly pricing: {
    readonly pricing_type: string;
    readonly amount: string | number;
    readonly currency: string;
    readonly sessions_count?: number | null;
    readonly free_trial_class_offered: boolean;
  };
  readonly schedule: {
    readonly schedule_type: string;
    readonly weekly_entries: Array<{
      readonly day_of_week_utc: number;
      readonly start_minutes_utc: number;
      readonly end_minutes_utc: number;
    }>;
    readonly languages: string[];
  };
  readonly _sort: StagingSortMeta;
}

interface StagingFixture {
  readonly meta: {
    readonly area_descendants: Record<string, string[]>;
  };
  readonly items: StagingFixtureItem[];
}

let cachedFixture: StagingFixture | null = null;
let cachedFixtureUrl: string | null = null;

/** Clears the in-memory fixture cache (for tests). */
export function clearStagingFixtureCacheForTests(): void {
  cachedFixture = null;
  cachedFixtureUrl = null;
}

export function resolveStagingSearchFixtureUrl(): string {
  const search = getSearchConfig();
  if (search.stagingSearchFixtureUrl) {
    return search.stagingSearchFixtureUrl;
  }
  const siteOrigin = getSiteConfig().siteOrigin.replace(/\/$/, '');
  if (siteOrigin) {
    return `${siteOrigin}/fixtures/activity_search_staging.json`;
  }
  return '';
}

async function loadStagingFixture(): Promise<StagingFixture> {
  const url = resolveStagingSearchFixtureUrl();
  if (!url) {
    throw new Error('Staging search fixture URL is not configured.');
  }
  if (cachedFixture && cachedFixtureUrl === url) {
    return cachedFixture;
  }

  const response = await fetch(url, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(
      `Failed to load staging search fixture (${response.status}) from ${url}`,
    );
  }

  cachedFixture = (await response.json()) as StagingFixture;
  cachedFixtureUrl = url;
  return cachedFixture;
}

function sortKey(item: StagingFixtureItem): [number, number, string] {
  return [
    item._sort.day_of_week_utc,
    item._sort.start_minutes_utc,
    item._sort.schedule_id,
  ];
}

function matchesItem(
  item: StagingFixtureItem,
  params: ActivitySearchParams,
  areaDescendants: Record<string, string[]>,
): boolean {
  if (params.activityId && item.activity.id !== params.activityId) {
    return false;
  }

  if (params.age !== undefined) {
    const ageMin = item.activity.age_min;
    const ageMax = item.activity.age_max;
    if (ageMin == null || ageMax == null) {
      return false;
    }
    if (params.age < ageMin || params.age > ageMax) {
      return false;
    }
  }

  if (params.areaId) {
    const allowed = areaDescendants[params.areaId] ?? [params.areaId];
    if (!allowed.includes(item.location.area_id)) {
      return false;
    }
  }

  if (params.categoryIds && params.categoryIds.length > 0) {
    const categoryId = item.activity.category_id ?? '';
    if (!params.categoryIds.includes(categoryId)) {
      return false;
    }
  }

  const status = item.organization.status;
  if (status === 'closed_permanently' || status === 'hidden') {
    return false;
  }

  return true;
}

function mapStagingListing(item: StagingFixtureItem): ActivityListing {
  const isTemplate = item.organization.description_source === 'template';
  return {
    activity: {
      id: item.activity.id,
      name: item.activity.name,
      description: isTemplate ? null : item.activity.description,
      nameTranslations: item.activity.name_translations ?? {},
      descriptionTranslations: isTemplate
        ? {}
        : item.activity.description_translations ?? {},
      ageMin: item.activity.age_min ?? null,
      ageMax: item.activity.age_max ?? null,
      categoryId: item.activity.category_id ?? null,
    },
    organization: {
      id: item.organization.id,
      name: item.organization.name,
      description: isTemplate ? null : item.organization.description ?? null,
      nameTranslations: item.organization.name_translations ?? {},
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
      lat: item.location.lat != null ? Number(item.location.lat) : null,
      lng: item.location.lng != null ? Number(item.location.lng) : null,
    },
    pricing: {
      pricingType: item.pricing.pricing_type,
      amount: Number(item.pricing.amount),
      currency: item.pricing.currency,
      sessionsCount: item.pricing.sessions_count ?? null,
      freeTrialClassOffered: item.pricing.free_trial_class_offered,
    },
    schedule: {
      scheduleType: item.schedule.schedule_type,
      weeklyEntries: item.schedule.weekly_entries.map((entry) => ({
        dayOfWeekUtc: entry.day_of_week_utc,
        startMinutesUtc: entry.start_minutes_utc,
        endMinutesUtc: entry.end_minutes_utc,
      })),
      languages: item.schedule.languages ?? [],
    },
  };
}

function decodeCursor(cursor: string): StagingSortMeta | null {
  try {
    const padding = '='.repeat((4 - (cursor.length % 4)) % 4);
    const raw = atob(cursor.replace(/-/g, '+').replace(/_/g, '/') + padding);
    const payload = JSON.parse(raw) as {
      schedule_id?: string;
      day_of_week_utc?: number;
      start_minutes_utc?: number;
    };
    if (
      payload.schedule_id == null
      || payload.day_of_week_utc == null
      || payload.start_minutes_utc == null
    ) {
      return null;
    }
    return {
      schedule_id: payload.schedule_id,
      day_of_week_utc: payload.day_of_week_utc,
      start_minutes_utc: payload.start_minutes_utc,
    };
  } catch {
    return null;
  }
}

function encodeCursor(sort: StagingSortMeta): string {
  const payload = JSON.stringify({
    schedule_id: sort.schedule_id,
    day_of_week_utc: sort.day_of_week_utc,
    start_minutes_utc: sort.start_minutes_utc,
  });
  return btoa(payload).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export async function fetchStagingActivitySearch(
  params: ActivitySearchParams,
): Promise<ActivitySearchResponse> {
  const fixture = await loadStagingFixture();
  const limit = params.limit ?? 50;
  const areaDescendants = fixture.meta.area_descendants ?? {};

  let matched = fixture.items.filter((item) =>
    matchesItem(item, params, areaDescendants),
  );
  matched = [...matched].sort((left, right) => {
    const leftKey = sortKey(left);
    const rightKey = sortKey(right);
    if (leftKey[0] !== rightKey[0]) {
      return leftKey[0] - rightKey[0];
    }
    if (leftKey[1] !== rightKey[1]) {
      return leftKey[1] - rightKey[1];
    }
    return leftKey[2].localeCompare(rightKey[2]);
  });

  let startIndex = 0;
  if (params.cursor) {
    const parsed = decodeCursor(params.cursor);
    if (parsed) {
      const cursorKey: [number, number, string] = [
        parsed.day_of_week_utc,
        parsed.start_minutes_utc,
        parsed.schedule_id,
      ];
      startIndex = matched.findIndex((item) => sortKey(item) > cursorKey);
      if (startIndex < 0) {
        startIndex = matched.length;
      }
    }
  }

  const slice = matched.slice(startIndex, startIndex + limit + 1);
  const hasMore = slice.length > limit;
  const page = slice.slice(0, limit);
  const last = page[page.length - 1];

  return {
    items: page.map(mapStagingListing),
    nextCursor: hasMore && last ? encodeCursor(last._sort) : null,
  };
}
