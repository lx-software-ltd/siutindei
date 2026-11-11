import type { Locale } from '@/content/locales';

import { listingVariants, listingVenues } from './group-listings';
import { listingTitle } from './listing-utils';
import type {
  ActivityListing,
  ActivityListingVariant,
  SearchPricing,
  WeeklyScheduleEntry,
} from './types';

/** The listing with its own location, pricing, and schedule moved to a venue. */
export function listingAtVenue(
  listing: ActivityListing,
  locationId: string | null,
): ActivityListing {
  const variants = venueVariants(listing, locationId);
  const first = variants[0];
  if (!first) {
    return listing;
  }
  return {
    ...listing,
    location: first.location,
    pricing: first.pricing,
    schedule: first.schedule,
    variants,
  };
}

export function venueVariants(
  listing: ActivityListing,
  locationId: string | null,
): readonly ActivityListingVariant[] {
  const all = listingVariants(listing);
  if (!locationId) {
    return all;
  }
  const atVenue = all.filter((variant) => variant.location.id === locationId);
  return atVenue.length > 0 ? atVenue : all;
}

export function venueWeeklyEntries(
  variants: readonly ActivityListingVariant[],
): readonly WeeklyScheduleEntry[] {
  return variants.flatMap((variant) => variant.schedule?.weeklyEntries ?? []);
}

export function venueLanguages(
  variants: readonly ActivityListingVariant[],
): readonly string[] {
  return [...new Set(variants.flatMap((variant) => variant.schedule?.languages ?? []))];
}

export function venueFreeTrial(variants: readonly ActivityListingVariant[]): boolean {
  return variants.some((variant) => variant.pricing?.freeTrialClassOffered);
}

export function venuePricings(
  variants: readonly ActivityListingVariant[],
): readonly SearchPricing[] {
  const seen = new Set<string>();
  const prices: SearchPricing[] = [];
  for (const variant of variants) {
    if (!variant.pricing) {
      continue;
    }
    const key = JSON.stringify(variant.pricing);
    if (!seen.has(key)) {
      seen.add(key);
      prices.push(variant.pricing);
    }
  }
  return prices;
}

export function venueCount(listing: ActivityListing): number {
  return listingVenues(listing).length;
}

/** A WhatsApp link that names the activity, or null when none is configured. */
export function buildEnquiryHref(
  whatsappUrl: string | undefined,
  listing: ActivityListing,
  locale: Locale,
): string | null {
  if (!whatsappUrl) {
    return null;
  }
  const title = listingTitle(locale, listing);
  const message = encodeURIComponent(
    locale === 'zh-HK'
      ? `你好，我想查詢「${title}」的詳情。`
      : `Hi, I would like to ask about "${title}".`,
  );
  const separator = whatsappUrl.includes('?') ? '&' : '?';
  return `${whatsappUrl}${separator}text=${message}`;
}

/** Description paragraphs, split on blank lines, with single breaks kept. */
export function descriptionParagraphs(text: string): readonly string[] {
  return text
    .replace(/\r\n/g, '\n')
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
}
