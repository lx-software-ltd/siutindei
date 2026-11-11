import type { Locale } from '@/content/locales';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';

import type { ActivityListing, SearchLocation } from './types';

/** "Ages 3–6", "Ages 3+", or "Up to 6 years". Null when neither bound is set. */
export function formatAgeRange(
  locale: Locale,
  ageMin: number | null,
  ageMax: number | null,
): string | null {
  const zh = locale === 'zh-HK';
  if (ageMin !== null && ageMax !== null) {
    if (ageMin === ageMax) {
      return zh ? `${ageMin}歲` : `Age ${ageMin}`;
    }
    return zh ? `${ageMin}–${ageMax}歲` : `Ages ${ageMin}–${ageMax}`;
  }
  if (ageMin !== null) {
    return zh ? `${ageMin}歲或以上` : `Ages ${ageMin}+`;
  }
  if (ageMax !== null) {
    return zh ? `${ageMax}歲或以下` : `Up to age ${ageMax}`;
  }
  return null;
}

export function listingAgeLabel(
  locale: Locale,
  listing: ActivityListing,
): string | null {
  return formatAgeRange(locale, listing.activity.ageMin, listing.activity.ageMax);
}

export function categoryLabelForListing(
  locale: Locale,
  listing: ActivityListing,
): string | null {
  const match = homeWizardChoices.activityTypes.find(
    (type) => type.categoryId === listing.activity.categoryId,
  );
  return match ? labelForLocale(match.labels, locale) : null;
}

export function categoryTypeIdForListing(listing: ActivityListing): string | null {
  return (
    homeWizardChoices.activityTypes.find(
      (type) => type.categoryId === listing.activity.categoryId,
    )?.id ?? null
  );
}

export function neighbourhoodLabelForLocation(
  locale: Locale,
  location: SearchLocation,
): string | null {
  const match = homeWizardChoices.neighbourhoods.find(
    (entry) => entry.areaId === location.areaId,
  );
  return match ? labelForLocale(match.labels, locale) : null;
}

export function regionLabelForLocation(
  locale: Locale,
  location: SearchLocation,
): string | null {
  const match = homeWizardChoices.regions.find(
    (region) =>
      region.areaId === location.regionAreaId || region.areaId === location.areaId,
  );
  return match ? labelForLocale(match.labels, locale) : null;
}

/** "Kennedy Town, Hong Kong Island", or whichever part is known. */
export function placeLabelForLocation(
  locale: Locale,
  location: SearchLocation,
): string | null {
  const parts = [
    neighbourhoodLabelForLocation(locale, location),
    regionLabelForLocation(locale, location),
  ].filter((part): part is string => Boolean(part));
  if (parts.length === 0) {
    return null;
  }
  return parts.join(locale === 'zh-HK' ? '，' : ', ');
}

/** The short place for a card: the neighbourhood, else the region. */
export function shortPlaceLabel(
  locale: Locale,
  location: SearchLocation,
): string | null {
  return (
    neighbourhoodLabelForLocation(locale, location) ??
    regionLabelForLocation(locale, location)
  );
}

/** A Google Maps directions link from the place id, pin, or address. */
export function directionsUrl(
  location: SearchLocation,
  placeId: string | null | undefined,
): string | null {
  const params = new URLSearchParams({ api: '1' });
  if (location.lat !== null && location.lng !== null) {
    params.set('destination', `${location.lat},${location.lng}`);
  } else if (location.address) {
    params.set('destination', location.address);
  } else {
    return null;
  }
  if (placeId) {
    params.set('destination_place_id', placeId);
  }
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

const LANGUAGE_LABELS: Record<string, { readonly en: string; readonly zh: string }> = {
  en: { en: 'English', zh: '英文' },
  yue: { en: 'Cantonese', zh: '廣東話' },
  zh: { en: 'Mandarin', zh: '普通話' },
  cmn: { en: 'Mandarin', zh: '普通話' },
  fr: { en: 'French', zh: '法文' },
  ja: { en: 'Japanese', zh: '日文' },
  ko: { en: 'Korean', zh: '韓文' },
  es: { en: 'Spanish', zh: '西班牙文' },
  de: { en: 'German', zh: '德文' },
};

export function languageLabel(locale: Locale, code: string): string {
  const entry = LANGUAGE_LABELS[code.toLowerCase()];
  if (!entry) {
    return code.toUpperCase();
  }
  return locale === 'zh-HK' ? entry.zh : entry.en;
}

export function listingLanguagesLabel(
  locale: Locale,
  languages: readonly string[],
): string | null {
  if (languages.length === 0) {
    return null;
  }
  const labels = [...new Set(languages.map((code) => languageLabel(locale, code)))];
  return labels.join(locale === 'zh-HK' ? '、' : ', ');
}
