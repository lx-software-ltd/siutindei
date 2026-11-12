import type { Locale } from '@/content/locales';

import type { WeeklyScheduleEntry } from './types';

/** Hong Kong is UTC+8 all year, with no daylight saving. */
const HONG_KONG_OFFSET_MINUTES = 8 * 60;
const MINUTES_PER_DAY = 24 * 60;
const DAYS_PER_WEEK = 7;

const SHORT_DAY_LABELS: Record<Locale, readonly string[]> = {
  en: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
  'zh-HK': ['週日', '週一', '週二', '週三', '週四', '週五', '週六'],
};

const LONG_DAY_LABELS: Record<Locale, readonly string[]> = {
  en: [
    'Sunday',
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
  ],
  'zh-HK': ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'],
};

/** A weekly session in Hong Kong time. `day` is 0 for Sunday. */
export interface HongKongSession {
  readonly day: number;
  readonly startMinutes: number;
  readonly endMinutes: number;
}

export function toHongKongSession(entry: WeeklyScheduleEntry): HongKongSession {
  const start =
    entry.dayOfWeekUtc * MINUTES_PER_DAY +
    entry.startMinutesUtc +
    HONG_KONG_OFFSET_MINUTES;
  return {
    day: Math.floor(start / MINUTES_PER_DAY) % DAYS_PER_WEEK,
    startMinutes: start % MINUTES_PER_DAY,
    endMinutes:
      (entry.endMinutesUtc + HONG_KONG_OFFSET_MINUTES) % MINUTES_PER_DAY,
  };
}

/** Monday first, the way Hong Kong timetables are read. */
function weekOrder(day: number): number {
  return (day + 6) % DAYS_PER_WEEK;
}

export function hongKongSessions(
  entries: readonly WeeklyScheduleEntry[],
): readonly HongKongSession[] {
  const seen = new Set<string>();
  const sessions: HongKongSession[] = [];
  for (const entry of entries) {
    const session = toHongKongSession(entry);
    const key = `${session.day}:${session.startMinutes}:${session.endMinutes}`;
    if (!seen.has(key)) {
      seen.add(key);
      sessions.push(session);
    }
  }
  return sessions.sort(
    (left, right) =>
      weekOrder(left.day) - weekOrder(right.day) ||
      left.startMinutes - right.startMinutes,
  );
}

export function formatClockTime(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
}

export function formatSessionTimes(session: HongKongSession): string {
  if (session.endMinutes === session.startMinutes) {
    return formatClockTime(session.startMinutes);
  }
  return `${formatClockTime(session.startMinutes)}–${formatClockTime(session.endMinutes)}`;
}

export function dayLabel(
  locale: Locale,
  day: number,
  style: 'short' | 'long' = 'short',
): string {
  const labels = style === 'long' ? LONG_DAY_LABELS[locale] : SHORT_DAY_LABELS[locale];
  return labels[day] ?? labels[0];
}

export function formatSession(locale: Locale, session: HongKongSession): string {
  return `${dayLabel(locale, session.day)} ${formatSessionTimes(session)}`;
}

export interface SessionsForDay {
  readonly day: number;
  readonly sessions: readonly HongKongSession[];
}

export function sessionsByDay(
  sessions: readonly HongKongSession[],
): readonly SessionsForDay[] {
  const groups: { day: number; sessions: HongKongSession[] }[] = [];
  for (const session of sessions) {
    const last = groups[groups.length - 1];
    if (last && last.day === session.day) {
      last.sessions.push(session);
    } else {
      groups.push({ day: session.day, sessions: [session] });
    }
  }
  return groups;
}

/** "Mon 10:00–11:00", plus "+2 more" when a listing has more sessions. */
export function formatScheduleSummary(
  locale: Locale,
  entries: readonly WeeklyScheduleEntry[],
): string | null {
  const sessions = hongKongSessions(entries);
  const first = sessions[0];
  if (!first) {
    return null;
  }
  const text = formatSession(locale, first);
  const extra = sessions.length - 1;
  if (extra <= 0) {
    return text;
  }
  return locale === 'zh-HK' ? `${text} 等${sessions.length}節` : `${text} +${extra} more`;
}
