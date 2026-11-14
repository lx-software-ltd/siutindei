import type { Locale } from '@/content/locales';

import { listingVariants } from './group-listings';
import { formatSessionTimes, hongKongSessions } from './schedule-format';
import type { ActivityListing, ActivityListingVariant, SearchSchedule } from './types';

const HONG_KONG_OFFSET_MS = 8 * 60 * 60 * 1000;
const MS_PER_DAY = 24 * 60 * 60 * 1000;
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

const SHORT_MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const;

interface CalendarDay {
  readonly year: number;
  readonly month: number;
  readonly day: number;
}

function parseIsoDate(value: string | null | undefined): CalendarDay | null {
  const match = value ? ISO_DATE.exec(value) : null;
  if (!match) {
    return null;
  }
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

function isoFromEpochDay(epochDay: number): string {
  return new Date(epochDay * MS_PER_DAY).toISOString().slice(0, 10);
}

function epochDay(value: string): number | null {
  const parsed = parseIsoDate(value);
  if (!parsed) {
    return null;
  }
  return Math.floor(Date.UTC(parsed.year, parsed.month - 1, parsed.day) / MS_PER_DAY);
}

/** Today's `YYYY-MM-DD` on the Hong Kong calendar. */
export function hongKongToday(now: Date = new Date()): string {
  return new Date(now.getTime() + HONG_KONG_OFFSET_MS).toISOString().slice(0, 10);
}

/**
 * The coming Saturday and Sunday in Hong Kong. On a Sunday only today
 * is left of the weekend.
 */
export function comingWeekend(today: string = hongKongToday()): {
  readonly dateFrom: string;
  readonly dateTo: string;
} {
  const start = epochDay(today) ?? epochDay(hongKongToday()) ?? 0;
  // Day 0 of the Unix epoch was a Thursday.
  const weekday = (start + 4) % 7;
  if (weekday === 0) {
    return { dateFrom: isoFromEpochDay(start), dateTo: isoFromEpochDay(start) };
  }
  const saturday = start + (6 - weekday);
  return { dateFrom: isoFromEpochDay(saturday), dateTo: isoFromEpochDay(saturday + 1) };
}

/** True when a dated session's last day is before `today`. */
export function sessionHasEnded(
  schedule: Pick<SearchSchedule, 'endsOn'> | null | undefined,
  today: string = hongKongToday(),
): boolean {
  return Boolean(schedule?.endsOn && schedule.endsOn < today);
}

/** "21–25 Jul", "28 Jul – 1 Aug", or "7月21日至25日". The year shows only across years. */
export function formatDateRange(
  locale: Locale,
  startsOn: string | null | undefined,
  endsOn: string | null | undefined,
): string | null {
  const start = parseIsoDate(startsOn);
  const end = parseIsoDate(endsOn) ?? start;
  if (!start || !end) {
    return null;
  }
  const sameYear = start.year === end.year;
  const sameMonth = sameYear && start.month === end.month;
  const sameDay = sameMonth && start.day === end.day;
  if (locale === 'zh-HK') {
    const first = `${sameYear ? '' : `${start.year}年`}${start.month}月${start.day}日`;
    if (sameDay) {
      return first;
    }
    const last = sameMonth
      ? `${end.day}日`
      : `${sameYear ? '' : `${end.year}年`}${end.month}月${end.day}日`;
    return `${first}至${last}`;
  }
  const month = (value: CalendarDay) => SHORT_MONTHS[value.month - 1];
  if (sameDay) {
    return `${start.day} ${month(start)}`;
  }
  if (sameMonth) {
    return `${start.day}–${end.day} ${month(end)}`;
  }
  if (sameYear) {
    return `${start.day} ${month(start)} – ${end.day} ${month(end)}`;
  }
  return `${start.day} ${month(start)} ${start.year} – ${end.day} ${month(end)} ${end.year}`;
}

/** Dated variants that have not ended, soonest first, one per start date. */
export function upcomingSessions(
  variants: readonly ActivityListingVariant[],
  today: string = hongKongToday(),
): readonly ActivityListingVariant[] {
  const byStart = new Map<string, ActivityListingVariant>();
  for (const variant of variants) {
    const startsOn = variant.schedule?.startsOn;
    if (!startsOn || sessionHasEnded(variant.schedule, today) || byStart.has(startsOn)) {
      continue;
    }
    byStart.set(startsOn, variant);
  }
  return [...byStart.values()].sort((left, right) =>
    (left.schedule?.startsOn ?? '').localeCompare(right.schedule?.startsOn ?? ''),
  );
}

/** The first day of the listing's next session, or null for an undated listing. */
export function nextSessionStart(
  listing: ActivityListing,
  today: string = hongKongToday(),
): string | null {
  return upcomingSessions(listingVariants(listing), today)[0]?.schedule?.startsOn ?? null;
}

/** Soonest next session first; undated listings keep their order after them. */
export function compareByNextSession(
  left: ActivityListing,
  right: ActivityListing,
  today: string = hongKongToday(),
): number {
  const leftStart = nextSessionStart(left, today);
  const rightStart = nextSessionStart(right, today);
  if (leftStart && rightStart) {
    return leftStart.localeCompare(rightStart);
  }
  if (leftStart) {
    return -1;
  }
  return rightStart ? 1 : 0;
}

/** "21–25 Jul · 09:00–15:00": the session's days, then its distinct times. */
export function formatDatedSession(
  locale: Locale,
  schedule: SearchSchedule,
): string | null {
  const range = formatDateRange(locale, schedule.startsOn, schedule.endsOn);
  if (!range) {
    return null;
  }
  const times = [
    ...new Set(hongKongSessions(schedule.weeklyEntries).map(formatSessionTimes)),
  ];
  return times.length > 0 ? `${range} · ${times.join(', ')}` : range;
}

/** The card line of a dated listing: its next session, or null when undated. */
export function nextSessionLabel(
  locale: Locale,
  listing: ActivityListing,
  today: string = hongKongToday(),
): string | null {
  const next = upcomingSessions(listingVariants(listing), today)[0]?.schedule;
  return next ? formatDatedSession(locale, next) : null;
}
