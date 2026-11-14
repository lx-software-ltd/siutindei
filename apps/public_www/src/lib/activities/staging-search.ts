import { stagingScopeAreaIds } from '@/lib/home-wizard/area-scope';
import { getSearchConfig, getSiteConfig } from '@/lib/site-config';

import { hideImportTemplateCopy } from './description-boilerplate';
import { mapActivityListing, parseListingKind } from './map-listing';
import { classPriceEquivalent } from './price-format';
import { hongKongToday } from './schedule-dates';
import { toHongKongSession } from './schedule-format';
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
    readonly category_root_id?: string | null;
    readonly kind?: string | null;
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
    readonly parent_verified?: boolean | null;
    readonly description_translations?: Record<string, string>;
  };
  readonly location: {
    readonly id: string;
    readonly area_id: string;
    readonly region_area_id?: string | null;
    readonly address?: string | null;
    readonly lat?: string | null;
    readonly lng?: string | null;
    readonly status?: string | null;
  };
  readonly pricing: {
    readonly pricing_type: string;
    readonly amount: string | number;
    readonly currency: string;
    readonly sessions_count?: number | null;
    readonly free_trial_class_offered: boolean;
  } | null;
  readonly schedule: {
    readonly schedule_type: string;
    readonly weekly_entries: Array<{
      readonly day_of_week_utc: number;
      readonly start_minutes_utc: number;
      readonly end_minutes_utc: number;
    }>;
    readonly languages: string[];
    readonly starts_on?: string | null;
    readonly ends_on?: string | null;
  } | null;
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
let cachedSortedPublishedItems: StagingFixtureItem[] | null = null;

/** Clears the in-memory fixture cache (for tests). */
export function clearStagingFixtureCacheForTests(): void {
  cachedFixture = null;
  cachedFixtureUrl = null;
  cachedSortedPublishedItems = null;
}

function isVisibleListing(item: StagingFixtureItem): boolean {
  const status = item.organization.status;
  if (status === 'closed_permanently' || status === 'hidden') {
    return false;
  }
  return item.location.status !== 'permanently_closed';
}

function sortedPublishedItems(fixture: StagingFixture): StagingFixtureItem[] {
  if (cachedSortedPublishedItems) {
    return cachedSortedPublishedItems;
  }
  const items = fixture.items
    .filter(isVisibleListing)
    .slice()
    .sort((left, right) => {
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
  cachedSortedPublishedItems = items;
  return items;
}

function resolveStagingSearchFixtureUrl(): string {
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
  cachedSortedPublishedItems = null;
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

  const scope = params.activityId ? null : stagingScopeAreaIds();
  if (scope && !scope.has(item.location.area_id)) {
    return false;
  }

  if (params.kinds && params.kinds.length > 0) {
    if (!params.kinds.includes(item.activity.kind ?? 'class')) {
      return false;
    }
  }

  if (item.activity.kind === 'eat' && !item.organization.parent_verified) {
    return false;
  }

  if (params.ageMin !== undefined || params.ageMax !== undefined) {
    const ageMin = item.activity.age_min;
    const ageMax = item.activity.age_max;
    if (ageMin == null || ageMax == null) {
      return false;
    }
    if (
      (params.ageMax !== undefined && ageMin > params.ageMax) ||
      (params.ageMin !== undefined && ageMax < params.ageMin)
    ) {
      return false;
    }
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
    const rootId = item.activity.category_root_id ?? '';
    if (!params.categoryIds.includes(categoryId) && !params.categoryIds.includes(rootId)) {
      return false;
    }
  }

  if (
    params.organizationIds &&
    params.organizationIds.length > 0 &&
    !params.organizationIds.includes(item.organization.id)
  ) {
    return false;
  }

  if (!matchesRefinements(item, params)) {
    return false;
  }

  const query = params.q?.trim().toLowerCase() ?? '';
  if (query.length >= 2 && !matchesText(item, query)) {
    return false;
  }

  const status = item.organization.status;
  if (status === 'closed_permanently' || status === 'hidden') {
    return false;
  }
  if (item.location.status === 'permanently_closed') {
    return false;
  }

  return true;
}

function matchesRefinements(
  item: StagingFixtureItem,
  params: ActivitySearchParams,
): boolean {
  const pricing = item.pricing;
  if (params.pricingType && pricing?.pricing_type !== params.pricingType) {
    return false;
  }
  if (params.freeTrial && !pricing?.free_trial_class_offered) {
    return false;
  }
  if (params.classPriceMax !== undefined) {
    const perClass = classPriceOf(item);
    if (perClass === null || perClass > params.classPriceMax) {
      return false;
    }
  }
  if (params.languages && params.languages.length > 0) {
    const languages = item.schedule?.languages ?? [];
    if (!params.languages.some((language) => languages.includes(language))) {
      return false;
    }
  }
  if (!datesMatch(item, params)) {
    return false;
  }
  if (params.daysOfWeekHkt && params.daysOfWeekHkt.length > 0) {
    const days = (item.schedule?.weekly_entries ?? []).map(
      (entry) =>
        toHongKongSession({
          dayOfWeekUtc: entry.day_of_week_utc,
          startMinutesUtc: entry.start_minutes_utc,
          endMinutesUtc: entry.end_minutes_utc,
        }).day,
    );
    if (!params.daysOfWeekHkt.some((day) => days.includes(day))) {
      return false;
    }
  }
  return true;
}

/** Twin of the API date rule: ended sessions drop out, a window keeps overlaps. */
function datesMatch(item: StagingFixtureItem, params: ActivitySearchParams): boolean {
  const startsOn = item.schedule?.starts_on ?? null;
  const endsOn = item.schedule?.ends_on ?? null;
  if (endsOn && endsOn < hongKongToday()) {
    return false;
  }
  if (params.dateFrom && endsOn && endsOn < params.dateFrom) {
    return false;
  }
  return !(params.dateTo && startsOn && startsOn > params.dateTo);
}

function classPriceOf(item: StagingFixtureItem): number | null {
  const pricing = item.pricing;
  if (!pricing) {
    return null;
  }
  return classPriceEquivalent(
    {
      pricingType: pricing.pricing_type,
      amount: Number(pricing.amount),
      currency: pricing.currency,
      sessionsCount: pricing.sessions_count ?? null,
      freeTrialClassOffered: pricing.free_trial_class_offered,
    },
    parseListingKind(item.activity.kind),
  );
}

function matchesText(item: StagingFixtureItem, query: string): boolean {
  const fields = [
    item.activity.name,
    item.organization.name,
    ...Object.values(item.activity.name_translations ?? {}),
    ...Object.values(item.organization.name_translations ?? {}),
  ];
  return fields.some((value) => value.toLowerCase().includes(query));
}

function listingFromFixture(
  item: StagingFixtureItem,
  view: 'card' | 'full',
): ActivityListing {
  const isTemplate = hideImportTemplateCopy(
    item.organization.description_source,
    item.organization.description,
  );
  return mapActivityListing(
    {
      ...item,
      activity: {
        ...item.activity,
        description: isTemplate ? null : item.activity.description,
        description_translations: isTemplate
          ? {}
          : item.activity.description_translations,
      },
      organization: {
        ...item.organization,
        description: isTemplate ? null : item.organization.description,
      },
    },
    view,
  );
}

function decodeCursorPayload(cursor: string): Record<string, unknown> | null {
  try {
    const padding = '='.repeat((4 - (cursor.length % 4)) % 4);
    const raw = atob(cursor.replace(/-/g, '+').replace(/_/g, '/') + padding);
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function encodeCursorPayload(payload: Record<string, unknown>): string {
  return btoa(JSON.stringify(payload))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

function decodeCursor(cursor: string): StagingSortMeta | null {
  try {
    const payload = decodeCursorPayload(cursor) as {
      schedule_id?: string;
      day_of_week_utc?: number;
      start_minutes_utc?: number;
    } | null;
    if (!payload) {
      return null;
    }
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

  const matched = sortedPublishedItems(fixture).filter((item) =>
    matchesItem(item, params, areaDescendants),
  );
  const total = params.includeTotal && !params.cursor
    ? new Set(matched.map((item) => item.activity.id)).size
    : null;

  if (params.sort === 'price') {
    return pageByPrice(matched, params, limit, total);
  }

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
    items: page.map((item) =>
      listingFromFixture(item, params.view === 'card' ? 'card' : 'full'),
    ),
    nextCursor: hasMore && last ? encodeCursor(last._sort) : null,
    total,
  };
}

function pageByPrice(
  matched: readonly StagingFixtureItem[],
  params: ActivitySearchParams,
  limit: number,
  total: number | null,
): ActivitySearchResponse {
  const ordered = matched
    .map((item, index) => ({ item, index, price: classPriceOf(item) }))
    .sort(
      (left, right) =>
        (left.price ?? Number.POSITIVE_INFINITY) -
          (right.price ?? Number.POSITIVE_INFINITY) || left.index - right.index,
    )
    .map((entry) => entry.item);
  const payload = params.cursor ? decodeCursorPayload(params.cursor) : null;
  const offset =
    payload && payload.sort === 'price' && typeof payload.offset === 'number'
      ? payload.offset
      : 0;
  const page = ordered.slice(offset, offset + limit);
  const hasMore = ordered.length > offset + limit;
  return {
    items: page.map((item) =>
      listingFromFixture(item, params.view === 'card' ? 'card' : 'full'),
    ),
    nextCursor: hasMore
      ? encodeCursorPayload({ sort: 'price', offset: offset + limit })
      : null,
    total,
  };
}
