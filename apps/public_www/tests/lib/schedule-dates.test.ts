import { describe, expect, it } from 'vitest';

import { listingMetaLine } from '@/components/sections/listings/listing-card';
import { groupListings } from '@/lib/activities/group-listings';
import { listingScheduleLabel } from '@/lib/activities/listing-utils';
import {
  compareByNextSession,
  comingWeekend,
  formatDateRange,
  hongKongToday,
  nextSessionStart,
  sessionHasEnded,
  upcomingSessions,
} from '@/lib/activities/schedule-dates';
import type { ActivityListing } from '@/lib/activities/types';

import { buildListing, buildSchedule } from '../helpers/listing-fixture';

/** Monday to Friday, 09:00–15:00 in Hong Kong. */
const CAMP_DAYS = [1, 2, 3, 4, 5].map((day) => ({
  dayOfWeekUtc: day,
  startMinutesUtc: 60,
  endMinutesUtc: 420,
}));

function camp(id: string, sessions: ReadonlyArray<[string, string]>): ActivityListing {
  const rows = sessions.map(([startsOn, endsOn]) =>
    buildListing({
      activity: { id, kind: 'camp' },
      schedule: buildSchedule({ weeklyEntries: CAMP_DAYS, startsOn, endsOn }),
    }),
  );
  return groupListings(rows)[0];
}

describe('schedule dates', () => {
  it('reads today on the Hong Kong calendar', () => {
    expect(hongKongToday(new Date('2026-11-13T15:59:00Z'))).toBe('2026-11-13');
    expect(hongKongToday(new Date('2026-11-13T16:00:00Z'))).toBe('2026-11-14');
  });

  it('finds the coming weekend, and only today on a Sunday', () => {
    expect(comingWeekend('2026-11-13')).toEqual({ dateFrom: '2026-11-14', dateTo: '2026-11-15' });
    expect(comingWeekend('2026-11-14')).toEqual({ dateFrom: '2026-11-14', dateTo: '2026-11-15' });
    expect(comingWeekend('2026-11-15')).toEqual({ dateFrom: '2026-11-15', dateTo: '2026-11-15' });
    expect(comingWeekend('2026-12-31')).toEqual({ dateFrom: '2027-01-02', dateTo: '2027-01-03' });
  });

  it('formats ranges in both locales and shows the year only across years', () => {
    expect(formatDateRange('en', '2027-07-21', '2027-07-25')).toBe('21–25 Jul');
    expect(formatDateRange('en', '2027-07-28', '2027-08-01')).toBe('28 Jul – 1 Aug');
    expect(formatDateRange('en', '2027-12-30', '2028-01-02')).toBe('30 Dec 2027 – 2 Jan 2028');
    expect(formatDateRange('en', '2027-07-21', '2027-07-21')).toBe('21 Jul');
    expect(formatDateRange('zh-HK', '2027-07-21', '2027-07-25')).toBe('7月21日至25日');
    expect(formatDateRange('zh-HK', '2027-07-28', '2027-08-01')).toBe('7月28日至8月1日');
    expect(formatDateRange('en', null, null)).toBeNull();
  });

  it('treats a session as ended only after its last day', () => {
    expect(sessionHasEnded({ endsOn: '2026-11-12' }, '2026-11-13')).toBe(true);
    expect(sessionHasEnded({ endsOn: '2026-11-13' }, '2026-11-13')).toBe(false);
    expect(sessionHasEnded({ endsOn: null }, '2026-11-13')).toBe(false);
  });

  it('keeps two sessions with the same hours apart and lists the upcoming ones first', () => {
    const listing = camp('camp-1', [
      ['2027-07-28', '2027-08-01'],
      ['2026-07-20', '2026-07-24'],
      ['2027-07-21', '2027-07-25'],
    ]);
    expect(listing.variants).toHaveLength(3);
    const upcoming = upcomingSessions(listing.variants ?? [], '2026-11-13');
    expect(upcoming.map((variant) => variant.schedule?.startsOn)).toEqual([
      '2027-07-21',
      '2027-07-28',
    ]);
    expect(nextSessionStart(listing, '2026-11-13')).toBe('2027-07-21');
  });

  it('labels a card with the next session and its hours', () => {
    const listing = camp('camp-1', [
      ['2027-07-28', '2027-08-01'],
      ['2027-07-21', '2027-07-25'],
    ]);
    expect(listingScheduleLabel('en', listing, '2026-11-13')).toBe('21–25 Jul · 09:00–15:00');
    expect(listingScheduleLabel('zh-HK', listing, '2026-11-13')).toBe('7月21日至25日 · 09:00–15:00');
    expect(listingScheduleLabel('en', buildListing(), '2026-11-13')).not.toContain('·');
  });

  it('puts the next session on a camp card', () => {
    const listing = camp('camp-1', [
      ['2099-07-27', '2099-07-31'],
      ['2099-07-20', '2099-07-24'],
    ]);
    expect(listingMetaLine('en', listing, '{count} locations').schedule).toBe(
      '20–24 Jul · 09:00–15:00',
    );
    const undated = buildListing({ activity: { kind: 'camp' } });
    expect(listingMetaLine('en', undated, '{count} locations').schedule).toBeNull();
  });

  it('sorts camps by next start and leaves undated listings after them', () => {
    const later = camp('later', [['2027-08-02', '2027-08-06']]);
    const sooner = camp('sooner', [['2027-07-05', '2027-07-09']]);
    const undated = buildListing({ activity: { id: 'undated', kind: 'camp' } });
    const sorted = [undated, later, sooner].sort((left, right) =>
      compareByNextSession(left, right, '2026-11-13'),
    );
    expect(sorted.map((listing) => listing.activity.id)).toEqual(['sooner', 'later', 'undated']);
  });
});
