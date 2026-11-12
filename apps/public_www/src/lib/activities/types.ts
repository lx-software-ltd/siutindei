export interface TranslationMap {
  readonly [locale: string]: string;
}

export interface SearchActivity {
  readonly id: string;
  readonly name: string;
  readonly description: string | null;
  readonly nameTranslations: TranslationMap;
  readonly descriptionTranslations: TranslationMap;
  readonly ageMin: number | null;
  readonly ageMax: number | null;
  readonly categoryId: string | null;
}

export interface OrganizationContact {
  readonly website: string | null;
  readonly email: string | null;
  readonly phoneCountryCode: string | null;
  readonly phoneNumber: string | null;
  readonly whatsapp: string | null;
  readonly facebook: string | null;
  readonly instagram: string | null;
  readonly tiktok: string | null;
  readonly twitter: string | null;
  readonly xiaohongshu: string | null;
  readonly wechat: string | null;
}

export interface FeedbackRating {
  readonly count: number;
  readonly averageStars: number;
}

export interface FeedbackLabel {
  readonly id: string;
  readonly name: string;
  readonly nameTranslations: TranslationMap;
}

export interface FeedbackReview {
  readonly id: string;
  readonly stars: number;
  readonly description: string | null;
  readonly labels: readonly FeedbackLabel[];
  readonly createdAt: string;
}

export interface SearchOrganization {
  readonly id: string;
  readonly name: string;
  readonly description: string | null;
  readonly nameTranslations: TranslationMap;
  readonly descriptionTranslations?: TranslationMap;
  readonly mediaUrls: readonly string[];
  readonly logoMediaUrl: string | null;
  readonly status?: string | null;
  readonly descriptionSource?: string | null;
  readonly placeId?: string | null;
  readonly parentVerified?: boolean;
  readonly updatedAt?: string | null;
  readonly contact?: OrganizationContact | null;
  readonly rating?: FeedbackRating | null;
  readonly reviews?: readonly FeedbackReview[];
}

export interface SearchLocation {
  readonly id: string;
  readonly areaId: string;
  readonly regionAreaId: string | null;
  readonly name?: string | null;
  readonly address: string | null;
  readonly lat: number | null;
  readonly lng: number | null;
  readonly status?: string | null;
}

export interface SearchPricing {
  readonly pricingType: string;
  readonly amount: number;
  readonly currency: string;
  readonly sessionsCount: number | null;
  readonly freeTrialClassOffered: boolean;
}

export interface WeeklyScheduleEntry {
  readonly dayOfWeekUtc: number;
  readonly startMinutesUtc: number;
  readonly endMinutesUtc: number;
}

export interface SearchSchedule {
  readonly scheduleType: string;
  readonly weeklyEntries: readonly WeeklyScheduleEntry[];
  readonly languages: readonly string[];
}

/** One search row of an activity: a venue with its price and schedule. */
export interface ActivityListingVariant {
  readonly location: SearchLocation;
  readonly pricing: SearchPricing | null;
  readonly schedule: SearchSchedule | null;
}

export interface ActivityListing {
  readonly activity: SearchActivity;
  readonly organization: SearchOrganization;
  readonly location: SearchLocation;
  readonly pricing: SearchPricing | null;
  readonly schedule: SearchSchedule | null;
  /** Every row of the activity, the first one being the fields above. */
  readonly variants?: readonly ActivityListingVariant[];
}

export interface ActivitySearchResponse {
  readonly items: readonly ActivityListing[];
  readonly nextCursor: string | null;
  readonly categoryMatch?: 'exact' | 'legacy_fallback';
  readonly total?: number | null;
}

export type ActivitySearchSort = 'time' | 'price';

export interface ActivitySearchParams {
  readonly age?: number;
  readonly areaId?: string;
  readonly categoryIds?: readonly string[];
  readonly activityId?: string;
  readonly organizationIds?: readonly string[];
  readonly pricingType?: string;
  readonly languages?: readonly string[];
  readonly daysOfWeekHkt?: readonly number[];
  readonly freeTrial?: boolean;
  readonly classPriceMax?: number;
  readonly sort?: ActivitySearchSort;
  readonly includeTotal?: boolean;
  readonly limit?: number;
  readonly cursor?: string;
  readonly q?: string;
  readonly view?: 'card' | 'full';
}
