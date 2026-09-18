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

export interface SearchOrganization {
  readonly id: string;
  readonly name: string;
  readonly description: string | null;
  readonly nameTranslations: TranslationMap;
  readonly mediaUrls: readonly string[];
  readonly logoMediaUrl: string | null;
  readonly status?: string | null;
  readonly descriptionSource?: string | null;
  readonly placeId?: string | null;
}

export interface SearchLocation {
  readonly id: string;
  readonly areaId: string;
  readonly regionAreaId: string | null;
  readonly address: string | null;
  readonly lat: number | null;
  readonly lng: number | null;
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

export interface ActivityListing {
  readonly activity: SearchActivity;
  readonly organization: SearchOrganization;
  readonly location: SearchLocation;
  readonly pricing: SearchPricing;
  readonly schedule: SearchSchedule;
}

export interface ActivitySearchResponse {
  readonly items: readonly ActivityListing[];
  readonly nextCursor: string | null;
}

export interface ActivitySearchParams {
  readonly age?: number;
  readonly areaId?: string;
  readonly categoryIds?: readonly string[];
  readonly activityId?: string;
  readonly limit?: number;
  readonly cursor?: string;
}
