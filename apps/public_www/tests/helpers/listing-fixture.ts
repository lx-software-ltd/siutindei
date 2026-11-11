import type {
  ActivityListing,
  SearchLocation,
  SearchPricing,
  SearchSchedule,
} from '@/lib/activities/types';

export const KOWLOON_AREA_ID = 'a1111111-1111-1111-1111-111111111102';
export const ARTS_CATEGORY_ID = 'c1111111-1111-1111-1111-111111111203';

export function buildLocation(overrides: Partial<SearchLocation> = {}): SearchLocation {
  return {
    id: 'loc-1',
    areaId: KOWLOON_AREA_ID,
    regionAreaId: KOWLOON_AREA_ID,
    name: null,
    address: '1 Example Road',
    lat: 22.3193,
    lng: 114.1694,
    status: 'open',
    ...overrides,
  };
}

export function buildPricing(overrides: Partial<SearchPricing> = {}): SearchPricing {
  return {
    pricingType: 'per_class',
    amount: 180,
    currency: 'hkd',
    sessionsCount: null,
    freeTrialClassOffered: false,
    ...overrides,
  };
}

export function buildSchedule(overrides: Partial<SearchSchedule> = {}): SearchSchedule {
  return {
    scheduleType: 'weekly',
    weeklyEntries: [{ dayOfWeekUtc: 1, startMinutesUtc: 120, endMinutesUtc: 180 }],
    languages: ['en'],
    ...overrides,
  };
}

export function buildListing(
  overrides: {
    readonly activity?: Partial<ActivityListing['activity']>;
    readonly organization?: Partial<ActivityListing['organization']>;
    readonly location?: Partial<SearchLocation>;
    readonly pricing?: SearchPricing | null;
    readonly schedule?: SearchSchedule | null;
  } = {},
): ActivityListing {
  return {
    activity: {
      id: 'act-1',
      name: 'Kowloon art',
      description: 'Paint together',
      nameTranslations: {},
      descriptionTranslations: {},
      ageMin: 3,
      ageMax: 6,
      categoryId: ARTS_CATEGORY_ID,
      ...overrides.activity,
    },
    organization: {
      id: 'org-1',
      name: 'Studio',
      description: null,
      nameTranslations: {},
      descriptionTranslations: {},
      mediaUrls: [],
      logoMediaUrl: null,
      status: 'operational',
      parentVerified: false,
      contact: null,
      rating: null,
      reviews: [],
      ...overrides.organization,
    },
    location: buildLocation(overrides.location),
    pricing: overrides.pricing === undefined ? buildPricing() : overrides.pricing,
    schedule: overrides.schedule === undefined ? buildSchedule() : overrides.schedule,
  };
}
