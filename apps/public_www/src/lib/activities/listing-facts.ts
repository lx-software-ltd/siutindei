import enContent from '@/content/en.json';
import type { Locale } from '@/content/locales';
import zhHKContent from '@/content/zh-HK.json';
import {
  homeWizardChoices,
  labelForLocale,
  type WizardActivityTypeOption,
} from '@/lib/home-wizard/choices';

import type { ActivityListing, SearchActivity, SearchLocation } from './types';

/** Kinds whose listings belong to a wizard topic. */
export const TOPIC_KINDS: ReadonlySet<SearchActivity['kind']> = new Set(['class', 'camp']);

/** A range that starts at birth and runs to adulthood says nothing about fit. */
export function isCatchAllAgeRange(ageMin: number | null, ageMax: number | null): boolean {
  return (ageMin ?? 0) <= 0 && (ageMax ?? Number.POSITIVE_INFINITY) >= 18;
}

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
  const { ageMin, ageMax, kind } = listing.activity;
  if (kind === 'place' || kind === 'eat' || isCatchAllAgeRange(ageMin, ageMax)) {
    return null;
  }
  return formatAgeRange(locale, ageMin, ageMax);
}

/** The wizard topic at the top of the category path, else the category itself. */
export function topicForListing(listing: ActivityListing): WizardActivityTypeOption | null {
  const { categoryRootId, categoryId } = listing.activity;
  const types = homeWizardChoices.activityTypes;
  return (
    types.find((type) => type.categoryId === categoryRootId) ??
    types.find((type) => type.categoryId === categoryId) ??
    null
  );
}

/** The topic for a class or camp; the category's own name for anything else. */
export function categoryLabelForListing(
  locale: Locale,
  listing: ActivityListing,
): string | null {
  const topic = topicForListing(listing);
  if (topic && TOPIC_KINDS.has(listing.activity.kind)) {
    return labelForLocale(topic.labels, locale);
  }
  const { categoryName, categoryNameTranslations } = listing.activity;
  const own = categoryNameTranslations[locale] ?? categoryName;
  return own ?? (topic ? labelForLocale(topic.labels, locale) : null);
}

export function categoryTypeIdForListing(listing: ActivityListing): string | null {
  return topicForListing(listing)?.id ?? null;
}

/** Fact keys a parent can check, per kind, in the order the page lists them. */
const FACT_KEYS: Readonly<Record<SearchActivity['kind'], readonly string[]>> = {
  place: [
    'toilets',
    'changing_table',
    'shade',
    'fenced',
    'stroller_access',
    'water_play',
    'lifeguard',
    'parking',
    'food_nearby',
  ],
  eat: [
    'high_chairs',
    'kids_menu',
    'changing_table',
    'stroller_access',
    'room_to_run',
    'outdoor_seating',
  ],
  class: ['drop_in', 'parent_stays', 'sen_friendly'],
  camp: ['drop_in', 'parent_stays', 'sen_friendly', 'lunch_included'],
  preschool: [],
};

export interface CheckedFact {
  readonly key: string;
  /** True when a parent saw it, false when a parent saw it missing. */
  readonly present: boolean;
}

/** The facts a parent checked for this kind. Unchecked keys are left out. */
export function checkedFacts(listing: ActivityListing): readonly CheckedFact[] {
  const { kind, facts } = listing.activity;
  return FACT_KEYS[kind]
    .filter((key) => typeof facts[key] === 'boolean')
    .map((key) => ({ key, present: facts[key] }));
}

type FactLabels = Readonly<Record<string, { readonly present: string; readonly absent: string }>>;

const FACT_LABELS: Readonly<Record<Locale, FactLabels>> = {
  en: enContent.activityDetail.factLabels,
  'zh-HK': zhHKContent.activityDetail.factLabels,
};

/** "High chairs", "No kids' menu": each checked fact, the missing ones included. */
export function checkedFactLabels(locale: Locale, listing: ActivityListing): readonly string[] {
  return checkedFacts(listing).flatMap((fact) => {
    const labels = FACT_LABELS[locale][fact.key];
    if (!labels) {
      return [];
    }
    return [fact.present ? labels.present : labels.absent];
  });
}

/** "November 2026" / "2026年11月", in Hong Kong time. Null for a bad date. */
export function formatMonthYear(locale: Locale, value: string | null | undefined): string | null {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat(locale === 'zh-HK' ? 'zh-HK' : 'en-GB', {
    month: 'long',
    year: 'numeric',
    timeZone: 'Asia/Hong_Kong',
  }).format(date);
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
