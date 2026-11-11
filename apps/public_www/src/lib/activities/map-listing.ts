import type { ActivityListing, TranslationMap } from './types';

export interface ActivityWireListing {
  activity: {
    id: string;
    name: string;
    description?: string | null;
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
    lat?: number | string | null;
    lng?: number | string | null;
    status?: string | null;
  };
  pricing?: {
    pricing_type: string;
    amount: number | string;
    currency: string;
    sessions_count?: number | null;
    free_trial_class_offered: boolean;
  } | null;
  schedule?: {
    schedule_type: string;
    weekly_entries?: Array<{
      day_of_week_utc: number;
      start_minutes_utc: number;
      end_minutes_utc: number;
    }>;
    languages?: string[];
  } | null;
}

function mapTranslationMap(
  value: Record<string, string> | undefined,
): TranslationMap {
  return value ?? {};
}

function toNumber(value: number | string | null | undefined): number | null {
  if (value == null || value === '') {
    return null;
  }
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function mapActivityListing(
  item: ActivityWireListing,
  view: 'card' | 'full' = 'full',
): ActivityListing {
  const card = view === 'card';
  const mediaUrls = item.organization.media_urls ?? [];
  const weeklyEntries = item.schedule?.weekly_entries ?? [];
  return {
    activity: {
      id: item.activity.id,
      name: item.activity.name,
      description: card ? null : item.activity.description ?? null,
      nameTranslations: mapTranslationMap(item.activity.name_translations),
      descriptionTranslations: card
        ? {}
        : mapTranslationMap(item.activity.description_translations),
      ageMin: item.activity.age_min ?? null,
      ageMax: item.activity.age_max ?? null,
      categoryId: item.activity.category_id ?? null,
    },
    organization: {
      id: item.organization.id,
      name: item.organization.name,
      description: card ? null : item.organization.description ?? null,
      nameTranslations: mapTranslationMap(item.organization.name_translations),
      mediaUrls: card ? mediaUrls.slice(0, 1) : mediaUrls,
      logoMediaUrl: item.organization.logo_media_url ?? null,
      status: item.organization.status ?? null,
      descriptionSource: item.organization.description_source ?? null,
      placeId: card ? null : item.organization.place_id ?? null,
    },
    location: {
      id: item.location.id,
      areaId: item.location.area_id,
      regionAreaId: item.location.region_area_id ?? null,
      address: item.location.address ?? null,
      lat: toNumber(item.location.lat),
      lng: toNumber(item.location.lng),
      status: item.location.status ?? 'open',
    },
    pricing: item.pricing
      ? {
          pricingType: item.pricing.pricing_type,
          amount: toNumber(item.pricing.amount) ?? 0,
          currency: item.pricing.currency,
          sessionsCount: item.pricing.sessions_count ?? null,
          freeTrialClassOffered: item.pricing.free_trial_class_offered,
        }
      : null,
    schedule: item.schedule
      ? {
          scheduleType: item.schedule.schedule_type,
          weeklyEntries: (card ? weeklyEntries.slice(0, 1) : weeklyEntries).map(
            (entry) => ({
              dayOfWeekUtc: entry.day_of_week_utc,
              startMinutesUtc: entry.start_minutes_utc,
              endMinutesUtc: entry.end_minutes_utc,
            }),
          ),
          languages: item.schedule.languages ?? [],
        }
      : null,
  };
}
