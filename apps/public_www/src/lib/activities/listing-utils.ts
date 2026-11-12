import type { Locale } from '@/content/locales';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';

import { descriptionIsImportBoilerplate } from './description-boilerplate';
import { formatListingPriceSummary } from './price-format';
import { formatScheduleSummary } from './schedule-format';
import type {
  ActivityListing,
  TranslationMap,
  WeeklyScheduleEntry,
} from './types';

/**
 * `zh-HK` reads `zh-HK`, then `zh`, then the base value. `en` reads `en`,
 * then the base value. English pages never show a `zh` translation.
 */
export function pickTranslation(
  locale: Locale,
  fallback: string,
  translations: TranslationMap,
): string {
  if (locale === 'zh-HK') {
    return translations['zh-HK'] || translations.zh || fallback;
  }
  return translations.en || fallback;
}

/** Every photo of the organisation, then the logo when there is no photo. */
export function listingImageUrls(listing: ActivityListing): readonly string[] {
  const photos = listing.organization.mediaUrls.filter(Boolean);
  if (photos.length > 0) {
    return photos;
  }
  return listing.organization.logoMediaUrl ? [listing.organization.logoMediaUrl] : [];
}

/** True when the only picture is the logo, which is shown contained. */
export function listingImageIsLogo(listing: ActivityListing): boolean {
  return (
    listing.organization.mediaUrls.filter(Boolean).length === 0 &&
    Boolean(listing.organization.logoMediaUrl)
  );
}

export function listingImageUrl(listing: ActivityListing): string | null {
  const orgMedia = listing.organization.mediaUrls[0];
  if (orgMedia) {
    return orgMedia;
  }
  return listing.organization.logoMediaUrl;
}

export function formatScheduleSnippet(
  locale: Locale,
  entries: readonly WeeklyScheduleEntry[],
): string | null {
  return formatScheduleSummary(locale, entries);
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
  return formatListingPriceSummary(locale, listing) ?? missingPriceLabel(locale);
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
