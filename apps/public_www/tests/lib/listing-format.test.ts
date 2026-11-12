import { describe, expect, it } from 'vitest';

import { groupListings, listingVenues } from '@/lib/activities/group-listings';
import { formatAgeRange, directionsUrl } from '@/lib/activities/listing-facts';
import {
  formatListingPrice,
  listingScheduleLabel,
  listingTitle,
  pickTranslation,
} from '@/lib/activities/listing-utils';
import {
  classPriceEquivalent,
  formatClassEquivalent,
  formatPricing,
} from '@/lib/activities/price-format';
import {
  hongKongSessions,
  sessionsByDay,
  toHongKongSession,
} from '@/lib/activities/schedule-format';

import {
  buildListing,
  buildLocation,
  buildPricing,
  buildSchedule,
} from '../helpers/listing-fixture';

describe('pickTranslation', () => {
  const translations = { zh: '中文名', 'zh-HK': '香港名' };

  it('never shows a zh translation on English pages', () => {
    expect(pickTranslation('en', 'Base', { zh: '中文名' })).toBe('Base');
    expect(pickTranslation('en', 'Base', { en: 'English', zh: '中文名' })).toBe(
      'English',
    );
  });

  it('reads zh-HK, then zh, then the base value on Chinese pages', () => {
    expect(pickTranslation('zh-HK', 'Base', translations)).toBe('香港名');
    expect(pickTranslation('zh-HK', 'Base', { zh: '中文名' })).toBe('中文名');
    expect(pickTranslation('zh-HK', 'Base', { en: 'English' })).toBe('Base');
  });

  it('shows the English name of a record that carries zh', () => {
    const listing = buildListing({
      activity: { name: 'Pottery', nameTranslations: { zh: '陶藝' } },
    });
    expect(listingTitle('en', listing)).toBe('Pottery');
    expect(listingTitle('zh-HK', listing)).toBe('陶藝');
  });
});

describe('Hong Kong time', () => {
  it('shows Monday 120 to 180 UTC as Mon 10:00–11:00', () => {
    const listing = buildListing();
    expect(listingScheduleLabel('en', listing)).toBe('Mon 10:00–11:00');
    expect(listingScheduleLabel('zh-HK', listing)).toBe('週一 10:00–11:00');
  });

  it('carries the day forward past midnight UTC+8', () => {
    expect(
      toHongKongSession({ dayOfWeekUtc: 5, startMinutesUtc: 17 * 60, endMinutesUtc: 18 * 60 }),
    ).toEqual({ day: 6, startMinutes: 60, endMinutes: 120 });
    expect(
      toHongKongSession({ dayOfWeekUtc: 6, startMinutesUtc: 20 * 60, endMinutesUtc: 21 * 60 }),
    ).toEqual({ day: 0, startMinutes: 4 * 60, endMinutes: 5 * 60 });
  });

  it('orders sessions Monday first and groups them by day', () => {
    const sessions = hongKongSessions([
      { dayOfWeekUtc: 0, startMinutesUtc: 60, endMinutesUtc: 120 },
      { dayOfWeekUtc: 1, startMinutesUtc: 300, endMinutesUtc: 360 },
      { dayOfWeekUtc: 1, startMinutesUtc: 120, endMinutesUtc: 180 },
      { dayOfWeekUtc: 1, startMinutesUtc: 120, endMinutesUtc: 180 },
    ]);
    expect(sessions.map((session) => session.day)).toEqual([1, 1, 0]);
    expect(sessionsByDay(sessions).map((group) => group.sessions.length)).toEqual([
      2,
      1,
    ]);
  });

  it('counts the extra sessions in the summary', () => {
    const listing = buildListing({
      schedule: buildSchedule({
        weeklyEntries: [
          { dayOfWeekUtc: 1, startMinutesUtc: 120, endMinutesUtc: 180 },
          { dayOfWeekUtc: 3, startMinutesUtc: 120, endMinutesUtc: 180 },
        ],
      }),
    });
    expect(listingScheduleLabel('en', listing)).toBe('Mon 10:00–11:00 +1 more');
  });
});

describe('prices', () => {
  it('describes what a term buys and its per-class equivalent', () => {
    const term = buildPricing({ pricingType: 'per_sessions', amount: 1600, sessionsCount: 8 });
    expect(formatPricing('en', term)).toBe('HK$1,600 / 8 classes');
    expect(formatPricing('zh-HK', term)).toBe('HK$1,600 / 8堂');
    expect(formatClassEquivalent('en', term)).toBe('About HK$200 per class');
    expect(classPriceEquivalent(term)).toBe(200);
  });

  it('keeps the plain suffixes', () => {
    expect(formatPricing('en', buildPricing())).toBe('HK$180 / class');
    expect(formatPricing('en', buildPricing({ pricingType: 'per_sessions' }))).toBe(
      'HK$180 / term',
    );
    expect(classPriceEquivalent(buildPricing({ pricingType: 'per_month' }))).toBeNull();
  });

  it('shows "From" the cheapest per-class price of a grouped listing', () => {
    const [grouped] = groupListings([
      buildListing({ pricing: buildPricing({ amount: 300 }) }),
      buildListing({
        location: { id: 'loc-2' },
        pricing: buildPricing({ amount: 200 }),
      }),
    ]);
    expect(formatListingPrice('en', grouped)).toBe('From HK$200 / class');
  });
});

describe('groupListings', () => {
  it('merges rows of one activity and keeps both venues', () => {
    const grouped = groupListings([
      buildListing(),
      buildListing({ activity: { id: 'act-2' } }),
      buildListing({ location: { id: 'loc-2', name: 'Second studio' } }),
      buildListing(),
    ]);
    expect(grouped.map((listing) => listing.activity.id)).toEqual(['act-1', 'act-2']);
    expect(grouped[0].location.id).toBe('loc-1');
    expect(listingVenues(grouped[0]).map((variant) => variant.location.id)).toEqual([
      'loc-1',
      'loc-2',
    ]);
    expect(grouped[0].variants).toHaveLength(2);
  });

  it('regroups already grouped listings without duplicating rows', () => {
    const once = groupListings([
      buildListing(),
      buildListing({ location: { id: 'loc-2' } }),
    ]);
    const twice = groupListings([...once, buildListing({ location: { id: 'loc-3' } })]);
    expect(twice[0].variants?.map((variant) => variant.location.id)).toEqual([
      'loc-1',
      'loc-2',
      'loc-3',
    ]);
  });
});

describe('facts', () => {
  it('formats age ranges', () => {
    expect(formatAgeRange('en', 3, 6)).toBe('Ages 3–6');
    expect(formatAgeRange('zh-HK', 3, 6)).toBe('3–6歲');
    expect(formatAgeRange('en', 3, null)).toBe('Ages 3+');
    expect(formatAgeRange('en', null, null)).toBeNull();
  });

  it('builds directions from the pin without a place id', () => {
    expect(directionsUrl(buildLocation(), null)).toBe(
      'https://www.google.com/maps/dir/?api=1&destination=22.3193%2C114.1694',
    );
    expect(
      directionsUrl(buildLocation({ lat: null, lng: null, address: null }), null),
    ).toBeNull();
  });
});
