import type { Locale } from '@/content/locales';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';

import { descriptionIsImportBoilerplate } from './description-boilerplate';
import type {
  ActivityListing,
  TranslationMap,
  WeeklyScheduleEntry,
} from './types';

const DAY_LABELS_EN = [
  'Sun',
  'Mon',
  'Tue',
  'Wed',
  'Thu',
  'Fri',
  'Sat',
] as const;

const DAY_LABELS_ZH = [
  '週日',
  '週一',
  '週二',
  '週三',
  '週四',
  '週五',
  '週六',
] as const;

export function pickTranslation(
  locale: Locale,
  fallback: string,
  translations: TranslationMap,
): string {
  if (locale === 'zh-HK' && translations['zh-HK']) {
    return translations['zh-HK'];
  }
  if (translations.zh) {
    return translations.zh;
  }
  if (translations.en) {
    return translations.en;
  }
  return fallback;
}

export function listingImageUrl(listing: ActivityListing): string | null {
  const orgMedia = listing.organization.mediaUrls[0];
  if (orgMedia) {
    return orgMedia;
  }
  return listing.organization.logoMediaUrl;
}

function formatMinutesAsTime(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
}

export function formatScheduleSnippet(
  locale: Locale,
  entries: readonly WeeklyScheduleEntry[],
): string | null {
  if (entries.length === 0) {
    return null;
  }
  const first = entries[0];
  const dayLabels = locale === 'zh-HK' ? DAY_LABELS_ZH : DAY_LABELS_EN;
  const day = dayLabels[first.dayOfWeekUtc] ?? DAY_LABELS_EN[0];
  return `${day} ${formatMinutesAsTime(first.startMinutesUtc)}`;
}

export function missingPriceLabel(locale: Locale): string {
  return locale === 'zh-HK' ? '價格待定' : 'Price on request';
}

export function missingScheduleLabel(locale: Locale): string {
  return locale === 'zh-HK' ? '時間待定' : 'Schedule to be confirmed';
}

export function listingScheduleLabel(
  locale: Locale,
  listing: ActivityListing,
): string | null {
  const snippet = listing.schedule
    ? formatScheduleSnippet(locale, listing.schedule.weeklyEntries)
    : null;
  return snippet ?? missingScheduleLabel(locale);
}

export function formatListingPrice(
  locale: Locale,
  listing: ActivityListing,
): string {
  const { pricing } = listing;
  if (!pricing) {
    return missingPriceLabel(locale);
  }
  if (pricing.pricingType === 'free') {
    return locale === 'zh-HK' ? '免費' : 'Free';
  }

  const amount = new Intl.NumberFormat(locale === 'zh-HK' ? 'zh-HK' : 'en-HK', {
    style: 'currency',
    currency: pricing.currency.toUpperCase(),
    maximumFractionDigits: 0,
  }).format(pricing.amount);

  const suffixMap: Record<string, { en: string; zh: string }> = {
    per_class: { en: ' / class', zh: ' / 堂' },
    per_sessions: { en: ' / term', zh: ' / 期' },
    per_hour: { en: ' / hr', zh: ' / 小時' },
    per_day: { en: ' / day', zh: ' / 天' },
    per_month: { en: ' / month', zh: ' / 月' },
    per_year: { en: ' / year', zh: ' / 年' },
  };
  const suffix = suffixMap[pricing.pricingType];
  if (!suffix) {
    return amount;
  }
  return `${amount}${locale === 'zh-HK' ? suffix.zh : suffix.en}`;
}

export function regionLabelForListing(
  locale: Locale,
  listing: ActivityListing,
): string | null {
  const regionId = listing.location.regionAreaId;
  if (!regionId) {
    return null;
  }
  const match = homeWizardChoices.regions.find(
    (region) => region.areaId === regionId,
  );
  if (!match) {
    return null;
  }
  return labelForLocale(match.labels, locale);
}

export function listingTitle(locale: Locale, listing: ActivityListing): string {
  return pickTranslation(
    locale,
    listing.activity.name,
    listing.activity.nameTranslations,
  );
}

export function isTemporarilyClosed(listing: ActivityListing): boolean {
  return (
    listing.organization.status === 'closed_temporarily' ||
    listing.location.status === 'temporarily_closed'
  );
}

export function isTemplateDescription(listing: ActivityListing): boolean {
  if (listing.organization.descriptionSource !== 'template') {
    return false;
  }
  const text = listing.organization.description ?? '';
  if (text.trim() === '') {
    return true;
  }
  return descriptionIsImportBoilerplate(text);
}

export function googleMapsPlaceUrl(placeId: string | null | undefined): string | null {
  if (!placeId) {
    return null;
  }
  return `https://www.google.com/maps/search/?api=1&query_place_id=${encodeURIComponent(placeId)}`;
}

export function listingOrgName(
  locale: Locale,
  listing: ActivityListing,
): string {
  return pickTranslation(
    locale,
    listing.organization.name,
    listing.organization.nameTranslations,
  );
}

export function matchesTextQuery(
  listing: ActivityListing,
  locale: Locale,
  query: string,
): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  const haystack = [
    listing.activity.name,
    listing.activity.description ?? '',
    listing.organization.name,
    pickTranslation(
      locale,
      listing.activity.name,
      listing.activity.nameTranslations,
    ),
  ]
    .join(' ')
    .toLowerCase();
  return haystack.includes(normalized);
}

export function sortListingsForDiscovery(
  listings: readonly ActivityListing[],
): readonly ActivityListing[] {
  return [...listings].sort((left, right) => {
    const leftHasImage = listingImageUrl(left) ? 1 : 0;
    const rightHasImage = listingImageUrl(right) ? 1 : 0;
    if (leftHasImage !== rightHasImage) {
      return rightHasImage - leftHasImage;
    }
    const leftTrial = left.pricing?.freeTrialClassOffered ?? false;
    const rightTrial = right.pricing?.freeTrialClassOffered ?? false;
    if (leftTrial !== rightTrial) {
      return leftTrial ? -1 : 1;
    }
    const leftAmount = left.pricing?.amount ?? Number.POSITIVE_INFINITY;
    const rightAmount = right.pricing?.amount ?? Number.POSITIVE_INFINITY;
    return leftAmount - rightAmount;
  });
}

export function groupListingsByRegion(
  listings: readonly ActivityListing[],
): Map<string, readonly ActivityListing[]> {
  const groups = new Map<string, ActivityListing[]>();
  for (const listing of listings) {
    const key = listing.location.regionAreaId ?? listing.location.areaId;
    const bucket = groups.get(key) ?? [];
    bucket.push(listing);
    groups.set(key, bucket);
  }
  return groups;
}
