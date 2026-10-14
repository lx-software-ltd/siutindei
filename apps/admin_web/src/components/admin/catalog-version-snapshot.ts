import { extractTranslations } from '../../lib/translations';
import type { OrganizationFormState } from '../shared/organizations/organization-form-utils';
import type { PricingFormState } from '../shared/pricing/pricing-types';
import {
  fromUtcWeekly,
  toLanguageCodes,
  type ScheduleFormState,
  type WeeklyEntryForm,
} from '../shared/schedules/schedule-form-utils';

export function snapshotRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function textFrom(value: unknown): string {
  if (value == null) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return '';
}

function applyText<T extends object>(
  form: T,
  snapshot: Record<string, unknown>,
  keys: (keyof T)[]
): T {
  const next = { ...form };
  for (const key of keys) {
    const name = String(key);
    if (name in snapshot) {
      next[key] = textFrom(snapshot[name]) as T[keyof T];
    }
  }
  return next;
}

const ORGANIZATION_TEXT_KEYS: (keyof OrganizationFormState)[] = [
  'name',
  'description',
  'email',
  'website',
  'phone_country_code',
  'phone_number',
  'status',
  'source',
  'source_id',
  'source_url',
  'source_note',
  'description_source',
  'whatsapp',
  'facebook',
  'instagram',
  'tiktok',
  'twitter',
  'xiaohongshu',
  'wechat',
];

export function organizationFormFromSnapshot(
  snapshot: Record<string, unknown>,
  fallback: OrganizationFormState
): OrganizationFormState {
  const next = applyText(fallback, snapshot, ORGANIZATION_TEXT_KEYS);
  if ('name_translations' in snapshot) {
    next.name_translations = extractTranslations(
      snapshotRecord(snapshot.name_translations) as Record<string, string> | null
    );
  }
  if ('description_translations' in snapshot) {
    next.description_translations = extractTranslations(
      snapshotRecord(snapshot.description_translations) as Record<string, string> | null
    );
  }
  return next;
}

export function ageBoundsFromSnapshot(
  value: unknown
): { min: string; max: string } | null {
  if (typeof value === 'string') {
    return boundsFromLiteral(value);
  }
  const record = snapshotRecord(value);
  if (!record) {
    return null;
  }
  return adjustBounds(
    record.lower,
    record.upper,
    record.lower_inc !== false,
    record.upper_inc !== false
  );
}

function boundsFromLiteral(literal: string): { min: string; max: string } | null {
  const text = literal.trim();
  if (text.length < 3) {
    return null;
  }
  const parts = text.slice(1, -1).split(',');
  if (parts.length !== 2) {
    return null;
  }
  const lower = parts[0]?.trim() ? Number(parts[0]) : null;
  const upper = parts[1]?.trim() ? Number(parts[1]) : null;
  if (
    (lower != null && !Number.isFinite(lower)) ||
    (upper != null && !Number.isFinite(upper))
  ) {
    return null;
  }
  return adjustBounds(lower, upper, text.startsWith('['), text.endsWith(']'));
}

function adjustBounds(
  lower: unknown,
  upper: unknown,
  lowerInc: boolean,
  upperInc: boolean
): { min: string; max: string } | null {
  let min = typeof lower === 'number' ? lower : null;
  let max = typeof upper === 'number' ? upper : null;
  if (min == null && max == null) {
    return null;
  }
  if (min != null && !lowerInc) {
    min += 1;
  }
  if (max != null && !upperInc) {
    max -= 1;
  }
  return { min: min == null ? '' : String(min), max: max == null ? '' : String(max) };
}

export interface ActivitySnapshotForm {
  name: string;
  description: string;
  name_translations: OrganizationFormState['name_translations'];
  description_translations: OrganizationFormState['description_translations'];
  age_min: string;
  age_max: string;
  source_url: string;
  source_note: string;
  category_id: string;
  org_id: string;
}

export function activityFormFromSnapshot<T extends ActivitySnapshotForm>(
  snapshot: Record<string, unknown>,
  fallback: T
): T {
  const next = applyText(fallback, snapshot, [
    'name',
    'description',
    'source_url',
    'source_note',
    'category_id',
    'org_id',
  ]);
  if ('name_translations' in snapshot) {
    next.name_translations = extractTranslations(
      snapshotRecord(snapshot.name_translations) as Record<string, string> | null
    );
  }
  if ('description_translations' in snapshot) {
    next.description_translations = extractTranslations(
      snapshotRecord(snapshot.description_translations) as Record<string, string> | null
    );
  }
  if ('age_range' in snapshot) {
    const bounds = ageBoundsFromSnapshot(snapshot.age_range);
    if (bounds) {
      next.age_min = bounds.min;
      next.age_max = bounds.max;
    }
  } else {
    next.age_min = applyText(
      { age_min: fallback.age_min, age_max: fallback.age_max },
      snapshot,
      ['age_min', 'age_max']
    ).age_min;
    next.age_max = applyText(
      { age_min: fallback.age_min, age_max: fallback.age_max },
      snapshot,
      ['age_min', 'age_max']
    ).age_max;
  }
  return next;
}

export interface LocationSnapshotForm {
  org_id: string;
  area_id: string;
  address: string;
  lat: string;
  lng: string;
}

export function locationFormFromSnapshot<T extends LocationSnapshotForm>(
  snapshot: Record<string, unknown>,
  fallback: T
): T {
  return applyText(fallback, snapshot, ['org_id', 'area_id', 'address', 'lat', 'lng']);
}

export function pricingFormFromSnapshot(
  snapshot: Record<string, unknown>,
  fallback: PricingFormState
): PricingFormState {
  const next = applyText(fallback, snapshot, [
    'activity_id',
    'location_id',
    'pricing_type',
    'amount',
    'currency',
    'sessions_count',
  ]);
  if ('free_trial_class_offered' in snapshot) {
    next.free_trial_class_offered = Boolean(snapshot.free_trial_class_offered);
  }
  if (next.pricing_type === 'free') {
    next.amount = '';
  }
  return next;
}

export function scheduleFormFromSnapshot(
  snapshot: Record<string, unknown>,
  fallback: ScheduleFormState
): ScheduleFormState {
  const next = applyText(fallback, snapshot, ['activity_id', 'location_id']);
  if ('languages' in snapshot && Array.isArray(snapshot.languages)) {
    next.languages = toLanguageCodes(
      snapshot.languages.filter((code): code is string => typeof code === 'string')
    );
  }
  const entries = weeklyEntriesFromSnapshot(snapshot.entries ?? snapshot.weekly_entries);
  if (entries) {
    next.weekly_entries = entries;
  }
  return next;
}

export function weeklyEntriesFromSnapshot(value: unknown): WeeklyEntryForm[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  return value.flatMap((entry, index) => {
    const row = snapshotRecord(entry);
    if (!row) {
      return [];
    }
    const day = Number(row.day_of_week_utc ?? row.day_of_week_local);
    const start = Number(row.start_minutes_utc ?? row.start_minutes_local);
    const end = Number(row.end_minutes_utc ?? row.end_minutes_local);
    if (![day, start, end].every(Number.isFinite)) {
      return [];
    }
    const local =
      'day_of_week_utc' in row || 'start_minutes_utc' in row
        ? fromUtcWeekly(day, start, end)
        : { dayOfWeek: day, startMinutes: start, endMinutes: end };
    return [
      {
        id: `snapshot-${day}-${start}-${index}`,
        day_of_week_local: String(local.dayOfWeek),
        start_minutes_local: String(local.startMinutes),
        end_minutes_local: String(local.endMinutes),
      },
    ];
  });
}

export function mediaFromSnapshot(snapshot: Record<string, unknown> | null): {
  urls: string[];
  logo: string | null;
} | null {
  if (!snapshot || !('media_urls' in snapshot)) {
    return null;
  }
  const urls = Array.isArray(snapshot.media_urls)
    ? snapshot.media_urls.filter((url): url is string => typeof url === 'string')
    : [];
  const logo =
    typeof snapshot.logo_media_url === 'string' ? snapshot.logo_media_url : null;
  return { urls, logo };
}

export function snapshotFieldText(key: string, value: unknown): string {
  if (key === 'age_range') {
    const bounds = ageBoundsFromSnapshot(value);
    if (!bounds || (!bounds.min && !bounds.max)) {
      return '—';
    }
    return `${bounds.min || '—'}–${bounds.max || '—'}`;
  }
  if (key === 'entries' || key === 'weekly_entries') {
    const entries = weeklyEntriesFromSnapshot(value);
    if (!entries || entries.length === 0) {
      return 'No timeslots';
    }
    return `${entries.length} timeslot${entries.length === 1 ? '' : 's'}`;
  }
  if (key === 'media_urls') {
    if (!Array.isArray(value) || value.length === 0) {
      return 'No media';
    }
    return value.filter((item) => typeof item === 'string').join(', ');
  }
  if (value == null || value === '') {
    return '—';
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? '—' : value.map((item) => textFrom(item) || '—').join(', ');
  }
  if (typeof value === 'object') {
    return textFrom((value as { name?: unknown }).name) || '—';
  }
  return textFrom(value) || '—';
}
