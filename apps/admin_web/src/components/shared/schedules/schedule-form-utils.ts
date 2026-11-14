import type { LanguageCode } from '../../../lib/translations';
import { languageOptions } from '../../../lib/translations';
import type { ActivitySchedule } from '../../../types/admin';

export interface WeeklyEntryForm {
  id: string;
  day_of_week_local: string;
  start_minutes_local: string;
  end_minutes_local: string;
}

export interface ScheduleFormState {
  activity_id: string;
  location_id: string;
  schedule_type: 'weekly';
  weekly_entries: WeeklyEntryForm[];
  languages: LanguageCode[];
  starts_on: string;
  ends_on: string;
}

export const emptyForm: ScheduleFormState = {
  activity_id: '',
  location_id: '',
  schedule_type: 'weekly',
  weekly_entries: [],
  languages: [],
  starts_on: '',
  ends_on: '',
};

export const dayOfWeekOptions = [
  { value: '0', label: 'Sunday' },
  { value: '1', label: 'Monday' },
  { value: '2', label: 'Tuesday' },
  { value: '3', label: 'Wednesday' },
  { value: '4', label: 'Thursday' },
  { value: '5', label: 'Friday' },
  { value: '6', label: 'Saturday' },
];

const minutesPerDay = 24 * 60;
const halfHourMinutes = 30;

const languageCodeSet = new Set<LanguageCode>(
  languageOptions.map((option) => option.code)
);

function scheduleLanguageCode(code: string): string {
  const folded = code.trim().toLowerCase().replace(/_/g, '-');
  if (folded === 'zh-hk') {
    return 'yue';
  }
  if (languageCodeSet.has(folded as LanguageCode)) {
    return folded;
  }
  return code;
}

export function toLanguageCodes(value?: string[] | null): LanguageCode[] {
  if (!value) return [];
  const codes: LanguageCode[] = [];
  for (const raw of value) {
    const code = scheduleLanguageCode(raw);
    if (!languageCodeSet.has(code as LanguageCode)) continue;
    const language = code as LanguageCode;
    if (!codes.includes(language)) codes.push(language);
  }
  return codes;
}

export function getLanguageOption(code: string) {
  const resolved = scheduleLanguageCode(code);
  return languageOptions.find((option) => option.code === resolved) ?? null;
}

export type ScheduleLanguageMark =
  | { kind: 'flag'; code: LanguageCode; label: string; flagSrc: string }
  | { kind: 'text'; code: string };

export function scheduleLanguageMarks(
  value?: string[] | null
): ScheduleLanguageMark[] {
  const marks: ScheduleLanguageMark[] = [];
  const seen = new Set<string>();
  for (const raw of value ?? []) {
    if (!raw) continue;
    const option = getLanguageOption(raw);
    const key = option?.code ?? raw;
    if (seen.has(key)) continue;
    seen.add(key);
    if (option) {
      marks.push({
        kind: 'flag',
        code: option.code,
        label: option.label,
        flagSrc: option.flagSrc,
      });
      continue;
    }
    marks.push({ kind: 'text', code: raw });
  }
  return marks;
}

function formatTimeLabel(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  const paddedHours = `${hours}`.padStart(2, '0');
  const paddedMinutes = `${mins}`.padStart(2, '0');
  return `${paddedHours}:${paddedMinutes}`;
}

const timeOptions = Array.from(
  { length: minutesPerDay / halfHourMinutes },
  (_, index) => {
    const minutes = index * halfHourMinutes;
    return { value: `${minutes}`, label: formatTimeLabel(minutes) };
  }
);

export function getTimeOptions(value: string) {
  if (!value) {
    return timeOptions;
  }

  if (timeOptions.some((option) => option.value === value)) {
    return timeOptions;
  }

  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return timeOptions;
  }

  if (numeric < 0 || numeric >= minutesPerDay) {
    return timeOptions;
  }

  const rounded = Math.round(numeric);
  const extraOption = {
    value,
    label: formatTimeLabel(rounded),
  };

  return [...timeOptions, extraOption].sort(
    (left, right) => Number(left.value) - Number(right.value)
  );
}

export function formatTimeRange(
  dayOfWeek: number,
  startMinutes: number,
  endMinutes: number
): string {
  const day = dayOfWeekOptions.find((option) => Number(option.value) === dayOfWeek);
  const dayLabel = day?.label ?? `Day ${dayOfWeek}`;
  return `${dayLabel} ${formatTimeLabel(startMinutes)}-${formatTimeLabel(endMinutes)}`;
}

function getLocalWeekdayBase(dayOfWeek: number): Date {
  const today = new Date();
  const todayDay = today.getDay();
  const delta = dayOfWeek - todayDay;
  const base = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate()
  );
  base.setDate(base.getDate() + delta);
  return base;
}

function getUtcWeekdayBase(dayOfWeek: number): Date {
  const today = new Date();
  const todayDay = today.getUTCDay();
  const delta = dayOfWeek - todayDay;
  const base = new Date(
    Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate())
  );
  base.setUTCDate(base.getUTCDate() + delta);
  return base;
}

function buildLocalDate(base: Date, minutes: number, dayOffset: number): Date {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return new Date(
    base.getFullYear(),
    base.getMonth(),
    base.getDate() + dayOffset,
    hours,
    mins
  );
}

function buildUtcDate(base: Date, minutes: number, dayOffset: number): Date {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return new Date(
    Date.UTC(
      base.getUTCFullYear(),
      base.getUTCMonth(),
      base.getUTCDate() + dayOffset,
      hours,
      mins
    )
  );
}

function localMinutes(date: Date): number {
  return date.getHours() * 60 + date.getMinutes();
}

function utcMinutes(date: Date): number {
  return date.getUTCHours() * 60 + date.getUTCMinutes();
}

export function toUtcWeekly(
  localDayOfWeek: number,
  localStartMinutes: number,
  localEndMinutes: number
) {
  const base = getLocalWeekdayBase(localDayOfWeek);
  const wraps = localStartMinutes > localEndMinutes;
  const startLocal = buildLocalDate(base, localStartMinutes, 0);
  const endLocal = buildLocalDate(base, localEndMinutes, wraps ? 1 : 0);
  return {
    dayOfWeek: startLocal.getUTCDay(),
    startMinutes: utcMinutes(startLocal),
    endMinutes: utcMinutes(endLocal),
  };
}

export function fromUtcWeekly(
  utcDayOfWeek: number,
  utcStartMinutes: number,
  utcEndMinutes: number
) {
  const base = getUtcWeekdayBase(utcDayOfWeek);
  const wraps = utcStartMinutes > utcEndMinutes;
  const startUtc = buildUtcDate(base, utcStartMinutes, 0);
  const endUtc = buildUtcDate(base, utcEndMinutes, wraps ? 1 : 0);
  const startLocal = new Date(startUtc.getTime());
  const endLocal = new Date(endUtc.getTime());
  return {
    dayOfWeek: startLocal.getDay(),
    startMinutes: localMinutes(startLocal),
    endMinutes: localMinutes(endLocal),
  };
}

function entryToForm(
  entry: ActivitySchedule['weekly_entries'][number],
  index: number
): WeeklyEntryForm {
  const localSchedule = fromUtcWeekly(
    entry.day_of_week_utc,
    entry.start_minutes_utc,
    entry.end_minutes_utc
  );
  return {
    id: `entry-${entry.day_of_week_utc}-${entry.start_minutes_utc}-${index}`,
    day_of_week_local: `${localSchedule.dayOfWeek}`,
    start_minutes_local: `${localSchedule.startMinutes}`,
    end_minutes_local: `${localSchedule.endMinutes}`,
  };
}

export function itemToForm(item: ActivitySchedule): ScheduleFormState {
  const weeklyEntries = (item.weekly_entries ?? []).map(entryToForm);
  return {
    activity_id: item.activity_id ?? '',
    location_id: item.location_id ?? '',
    schedule_type: 'weekly',
    weekly_entries: weeklyEntries,
    languages: toLanguageCodes(item.languages),
    starts_on: item.starts_on ?? '',
    ends_on: item.ends_on ?? '',
  };
}

const isoDatePattern = /^\d{4}-\d{2}-\d{2}$/;
const msPerDay = 24 * 60 * 60 * 1000;

function isoDayNumber(value: string): number | null {
  if (!isoDatePattern.test(value)) return null;
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) ? Math.floor(time / msPerDay) : null;
}

export function sessionDatesError(startsOn: string, endsOn: string): string {
  if (!startsOn && !endsOn) return '';
  if (!startsOn) return 'Set the first day, or clear the last day.';
  if (!endsOn) return 'Set the last day, or clear the first day.';
  const start = isoDayNumber(startsOn);
  const end = isoDayNumber(endsOn);
  if (start === null || end === null) return 'Use a full date.';
  if (end < start) return 'The last day must be on or after the first day.';
  return '';
}

/** Weekdays (0 = Sunday) between two ISO dates, inclusive. */
export function weekdaysBetween(startsOn: string, endsOn: string): Set<number> {
  const days = new Set<number>();
  const start = isoDayNumber(startsOn);
  const end = isoDayNumber(endsOn);
  if (start === null || end === null) return days;
  for (let day = start; day <= end && days.size < 7; day += 1) {
    // Day 0 of the Unix epoch was a Thursday.
    days.add((day + 4) % 7);
  }
  return days;
}

export function daysOutsideSessionError(form: ScheduleFormState): string {
  if (!form.starts_on || !form.ends_on) return '';
  const sessionDays = weekdaysBetween(form.starts_on, form.ends_on);
  const outside = form.weekly_entries.some(
    (entry) => !sessionDays.has(Number(entry.day_of_week_local))
  );
  return outside ? 'Every day must fall between the first and last day.' : '';
}

const sessionDateFormat = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
});

export function formatSessionDates(
  startsOn?: string | null,
  endsOn?: string | null
): string {
  if (!startsOn || !endsOn) return '';
  const start = isoDayNumber(startsOn);
  const end = isoDayNumber(endsOn);
  if (start === null || end === null) return '';
  const first = sessionDateFormat.format(new Date(start * msPerDay));
  if (start === end) return first;
  return `${first} – ${sessionDateFormat.format(new Date(end * msPerDay))}`;
}

export function getDayLabel(dayOfWeek: number): string {
  const option = dayOfWeekOptions.find((item) => Number(item.value) === dayOfWeek);
  return option?.label ?? `${dayOfWeek}`;
}

export function formatTimeLabelForMinutes(minutes: number): string {
  return formatTimeLabel(minutes);
}
