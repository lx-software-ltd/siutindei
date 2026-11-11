import { readFileSync } from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  clearStagingFixtureCacheForTests,
  fetchStagingActivitySearch,
} from '@/lib/activities/staging-search';
import { classPriceEquivalent } from '@/lib/activities/price-format';
import { clearSearchAreaScopeCacheForTests } from '@/lib/home-wizard/area-scope';

const fixturePath = path.resolve(
  __dirname,
  '../../../../shared/fixtures/activity_search_staging.json',
);

const LFS_POINTER_PREFIX = 'version https://git-lfs.github.com/spec/v1';

function readFixtureBody(): string {
  const body = readFileSync(fixturePath, 'utf8');
  if (body.startsWith(LFS_POINTER_PREFIX)) {
    throw new Error(
      'activity_search_staging.json is a Git LFS pointer; run git lfs pull',
    );
  }
  return body;
}

describe('fetchStagingActivitySearch', () => {
  beforeAll(() => {
    process.env.NEXT_PUBLIC_SITE_ORIGIN = 'http://localhost:3000';
    const body = readFixtureBody();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('activity_search_staging.json')) {
          return new Response(body, {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );
  });

  afterEach(() => {
    clearStagingFixtureCacheForTests();
    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
    clearSearchAreaScopeCacheForTests();
  });

  it('returns at least 3000 listings without filters', async () => {
    const response = await fetchStagingActivitySearch({ limit: 5000 });
    expect(response.items.length).toBeGreaterThanOrEqual(3000);
  });

  it('filters by wizard category and age', async () => {
    const response = await fetchStagingActivitySearch({
      age: 4,
      categoryIds: ['c1111111-1111-1111-1111-111111111201'],
      limit: 20,
    });
    expect(response.items.length).toBe(20);
    for (const item of response.items) {
      expect(item.activity.categoryId).toBe(
        'c1111111-1111-1111-1111-111111111201',
      );
      expect(item.activity.ageMin).toBeLessThanOrEqual(4);
      expect(item.activity.ageMax).toBeGreaterThanOrEqual(4);
      expect(item.schedule?.languages).toEqual(['en']);
    }
  });

  it('applies organiser, free trial, day, price, sort, and total like the API', async () => {
    const all = await fetchStagingActivitySearch({ limit: 50, includeTotal: true });
    expect(all.total).toBeGreaterThanOrEqual(3000);

    const organizationId = all.items[0].organization.id;
    const byOrganiser = await fetchStagingActivitySearch({
      organizationIds: [organizationId],
      limit: 50,
    });
    expect(byOrganiser.items.length).toBeGreaterThan(0);
    expect(byOrganiser.items.every((item) => item.organization.id === organizationId)).toBe(true);

    const trial = await fetchStagingActivitySearch({ freeTrial: true, limit: 20 });
    expect(trial.items.every((item) => item.pricing?.freeTrialClassOffered)).toBe(true);

    const weekend = await fetchStagingActivitySearch({ daysOfWeekHkt: [0, 6], limit: 20 });
    for (const item of weekend.items) {
      const days = (item.schedule?.weeklyEntries ?? []).map((entry) => {
        const minutes = entry.dayOfWeekUtc * 1440 + entry.startMinutesUtc + 480;
        return Math.floor(minutes / 1440) % 7;
      });
      expect(days.some((day) => day === 0 || day === 6)).toBe(true);
    }

    const cheapest = await fetchStagingActivitySearch({
      sort: 'price',
      classPriceMax: 300,
      limit: 20,
      includeTotal: true,
    });
    const prices = cheapest.items.map((item) =>
      item.pricing ? classPriceEquivalent(item.pricing) : null,
    );
    expect(cheapest.items.length).toBeGreaterThan(0);
    expect(prices.every((price) => price !== null && price <= 300)).toBe(true);
    expect([...prices].sort((a, b) => (a ?? 0) - (b ?? 0))).toEqual(prices);
    expect(cheapest.total).toBeGreaterThanOrEqual(cheapest.items.length);
    expect(cheapest.nextCursor === null || cheapest.items.length === 20).toBe(true);
  });

  it('filters names with q and omits detail fields in card view', async () => {
    const first = await fetchStagingActivitySearch({ limit: 1 });
    const name = first.items[0]?.activity.name ?? '';
    const needle = name.slice(0, Math.min(12, name.length));
    expect(needle.length).toBeGreaterThanOrEqual(2);

    const response = await fetchStagingActivitySearch({
      q: needle,
      view: 'card',
      limit: 5,
    });
    expect(response.items.length).toBeGreaterThan(0);
    for (const item of response.items) {
      const haystack = [
        item.activity.name,
        item.organization.name,
        ...Object.values(item.activity.nameTranslations),
        ...Object.values(item.organization.nameTranslations),
      ]
        .join('\n')
        .toLowerCase();
      expect(haystack).toContain(needle.toLowerCase());
      expect(item.activity.description).toBeNull();
      expect(item.organization.placeId).toBeNull();
      expect(item.organization.mediaUrls.length).toBeLessThanOrEqual(1);
      expect(item.schedule?.weeklyEntries.length ?? 0).toBeLessThanOrEqual(1);
    }
  });

  it('hides fixture rows outside the scope but still opens a direct activity', async () => {
    const first = await fetchStagingActivitySearch({ limit: 1 });
    const activityId = first.items[0]?.activity.id ?? '';
    expect(activityId).not.toBe('');

    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'not-a-place';
    clearSearchAreaScopeCacheForTests();

    const hidden = await fetchStagingActivitySearch({ limit: 5 });
    expect(hidden.items).toHaveLength(0);

    const direct = await fetchStagingActivitySearch({
      activityId,
      limit: 1,
    });
    expect(direct.items[0]?.activity.id).toBe(activityId);
  });
});
