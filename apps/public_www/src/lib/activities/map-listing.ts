import type {
  ActivityListing,
  FeedbackRating,
  ListingFacts,
  ListingKind,
  FeedbackReview,
  OrganizationContact,
  TranslationMap,
} from './types';

interface ContactWire {
  website?: string | null;
  email?: string | null;
  phone_country_code?: string | null;
  phone_number?: string | null;
  whatsapp?: string | null;
  facebook?: string | null;
  instagram?: string | null;
  tiktok?: string | null;
  twitter?: string | null;
  xiaohongshu?: string | null;
  wechat?: string | null;
}

interface ReviewWire {
  id: string;
  stars: number;
  description?: string | null;
  labels?: Array<{
    id: string;
    name: string;
    name_translations?: Record<string, string>;
  }>;
  created_at: string;
}

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
    kind?: string | null;
    facts?: Record<string, unknown> | null;
    category_root_id?: string | null;
    category_name?: string | null;
    category_name_translations?: Record<string, string>;
  };
  organization: {
    id: string;
    name: string;
    description?: string | null;
    name_translations?: Record<string, string>;
    description_translations?: Record<string, string>;
    media_urls?: string[];
    logo_media_url?: string | null;
    status?: string | null;
    description_source?: string | null;
    place_id?: string | null;
    parent_verified?: boolean | null;
    parent_verified_at?: string | null;
    updated_at?: string | null;
    contact?: ContactWire | null;
    rating?: { count: number; average_stars: number | string } | null;
    reviews?: ReviewWire[];
  };
  location: {
    id: string;
    area_id: string;
    region_area_id?: string | null;
    name?: string | null;
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

function blankToNull(value: string | null | undefined): string | null {
  const trimmed = value?.trim() ?? '';
  return trimmed === '' ? null : trimmed;
}

const LISTING_KINDS: readonly ListingKind[] = ['class', 'camp', 'place', 'preschool', 'eat'];

/** An old snapshot or a card row without a kind is a class. */
export function parseListingKind(value: string | null | undefined): ListingKind {
  return LISTING_KINDS.find((kind) => kind === value) ?? 'class';
}

function mapFacts(value: Record<string, unknown> | null | undefined): ListingFacts {
  const facts: Record<string, boolean> = {};
  for (const [key, seen] of Object.entries(value ?? {})) {
    if (typeof seen === 'boolean') {
      facts[key] = seen;
    }
  }
  return facts;
}

function mapContact(
  value: ContactWire | null | undefined,
): OrganizationContact | null {
  if (!value) {
    return null;
  }
  const contact: OrganizationContact = {
    website: blankToNull(value.website),
    email: blankToNull(value.email),
    phoneCountryCode: blankToNull(value.phone_country_code),
    phoneNumber: blankToNull(value.phone_number),
    whatsapp: blankToNull(value.whatsapp),
    facebook: blankToNull(value.facebook),
    instagram: blankToNull(value.instagram),
    tiktok: blankToNull(value.tiktok),
    twitter: blankToNull(value.twitter),
    xiaohongshu: blankToNull(value.xiaohongshu),
    wechat: blankToNull(value.wechat),
  };
  return Object.values(contact).some((entry) => entry !== null) ? contact : null;
}

function mapRating(
  value: { count: number; average_stars: number | string } | null | undefined,
): FeedbackRating | null {
  const average = toNumber(value?.average_stars);
  if (!value || !value.count || average === null) {
    return null;
  }
  return { count: value.count, averageStars: average };
}

function mapReviews(value: ReviewWire[] | undefined): readonly FeedbackReview[] {
  return (value ?? []).map((review) => ({
    id: review.id,
    stars: review.stars,
    description: blankToNull(review.description),
    labels: (review.labels ?? []).map((label) => ({
      id: label.id,
      name: label.name,
      nameTranslations: mapTranslationMap(label.name_translations),
    })),
    createdAt: review.created_at,
  }));
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
      kind: parseListingKind(item.activity.kind),
      facts: card ? {} : mapFacts(item.activity.facts),
      categoryRootId: item.activity.category_root_id ?? item.activity.category_id ?? null,
      categoryName: blankToNull(item.activity.category_name),
      categoryNameTranslations: mapTranslationMap(item.activity.category_name_translations),
    },
    organization: {
      id: item.organization.id,
      name: item.organization.name,
      description: card ? null : item.organization.description ?? null,
      nameTranslations: mapTranslationMap(item.organization.name_translations),
      descriptionTranslations: card
        ? {}
        : mapTranslationMap(item.organization.description_translations),
      mediaUrls: card ? mediaUrls.slice(0, 1) : mediaUrls,
      logoMediaUrl: item.organization.logo_media_url ?? null,
      status: item.organization.status ?? null,
      descriptionSource: item.organization.description_source ?? null,
      placeId: card ? null : item.organization.place_id ?? null,
      parentVerified: item.organization.parent_verified === true,
      parentVerifiedAt:
        item.organization.parent_verified === true
          ? item.organization.parent_verified_at ?? null
          : null,
      updatedAt: item.organization.updated_at ?? null,
      contact: card ? null : mapContact(item.organization.contact),
      rating: mapRating(item.organization.rating),
      reviews: card ? [] : mapReviews(item.organization.reviews),
    },
    location: {
      id: item.location.id,
      areaId: item.location.area_id,
      regionAreaId: item.location.region_area_id ?? null,
      name: blankToNull(item.location.name),
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
