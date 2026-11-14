import type { Locale } from '@/content/locales';
import { homeWizardChoices, kindOption, labelForLocale } from '@/lib/home-wizard/choices';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

import { categoryLandingPath } from './activity-href';
import { listingVenues } from './group-listings';
import { kindPageForKind } from './kind-pages';
import {
  categoryLabelForListing,
  categoryTypeIdForListing,
  isCatchAllAgeRange,
  listingAgeLabel,
  placeLabelForLocation,
  shortPlaceLabel,
  TOPIC_KINDS,
} from './listing-facts';
import {
  isTemplateDescription,
  listingOrgName,
  listingTitle,
  pickTranslation,
} from './listing-utils';
import { buildSearchPageHref } from './map-search-url';
import { DEFAULT_SEARCH_FILTERS } from './search-params';
import type { ActivityListing } from './types';

export interface ActivityBreadcrumbItem {
  readonly label: string;
  readonly href: string;
}

interface BreadcrumbCopy {
  readonly homeLabel: string;
  readonly searchLabel: string;
}

/**
 * Home, the activities hub, the topic for a class or camp or else the
 * kind (its landing page when there is one, else a search), then the
 * neighbourhood search.
 */
export function activityBreadcrumbItems(
  locale: Locale,
  listing: ActivityListing,
  copy: BreadcrumbCopy,
  landingTypeIds: readonly string[],
): readonly ActivityBreadcrumbItem[] {
  const items: ActivityBreadcrumbItem[] = [
    { label: copy.homeLabel, href: localizePath(ROUTES.home, locale) },
    { label: copy.searchLabel, href: localizePath(ROUTES.activities, locale) },
  ];
  const kind = listing.activity.kind;
  const typeId = TOPIC_KINDS.has(kind) ? categoryTypeIdForListing(listing) : null;
  const categoryLabel = categoryLabelForListing(locale, listing);
  const kindPage = kindPageForKind(kind);
  if (typeId && categoryLabel) {
    items.push({
      label: categoryLabel,
      href: landingTypeIds.includes(typeId)
        ? categoryLandingPath(locale, typeId)
        : buildSearchPageHref(
            locale,
            { ...DEFAULT_SEARCH_FILTERS, activityTypeIds: [typeId] },
            { view: 'list' },
          ),
    });
  } else if (kindPage && (landingTypeIds.includes(kindPage.slug) || kindOption(kind))) {
    items.push({
      label: labelForLocale(kindPage.labels, locale),
      href: landingTypeIds.includes(kindPage.slug)
        ? categoryLandingPath(locale, kindPage.slug)
        : buildSearchPageHref(locale, { ...DEFAULT_SEARCH_FILTERS, kind }, { view: 'list' }),
    });
  }
  const neighbourhood = homeWizardChoices.neighbourhoods.find(
    (entry) => entry.areaId === listing.location.areaId,
  );
  const place = shortPlaceLabel(locale, listing.location);
  if (neighbourhood && place) {
    items.push({
      label: place,
      href: buildSearchPageHref(
        locale,
        {
          ...DEFAULT_SEARCH_FILTERS,
          regionId: neighbourhood.regionId,
          neighbourhoodId: neighbourhood.id,
        },
        { view: 'list' },
      ),
    });
  }
  return items;
}

export function listingDescription(locale: Locale, listing: ActivityListing): string {
  if (isTemplateDescription(listing)) {
    return '';
  }
  return pickTranslation(
    locale,
    listing.activity.description ?? '',
    listing.activity.descriptionTranslations,
  ).trim();
}

function firstSentence(text: string): string {
  const match = /^(.+?[.!?。！？])(\s|$)/u.exec(text);
  return (match ? match[1] : text).trim();
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  const cut = text.slice(0, maxLength - 1);
  const lastSpace = cut.lastIndexOf(' ');
  return `${(lastSpace > maxLength * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
}

export const META_DESCRIPTION_MAX_LENGTH = 160;

function metaLead(locale: Locale, listing: ActivityListing): string {
  const category = categoryLabelForListing(locale, listing);
  const ages = listingAgeLabel(locale, listing);
  const place = shortPlaceLabel(locale, listing.location);
  const organisation = listingOrgName(locale, listing);
  if (locale === 'zh-HK') {
    return [
      `${place ?? ''}${category ?? ''}活動`,
      ages ? `適合${ages}` : null,
      `由${organisation}提供。`,
    ]
      .filter(Boolean)
      .join('，');
  }
  const what = [
    category ?? 'Activity',
    place ? `in ${place}` : null,
    ages ? `for ${ages.charAt(0).toLowerCase()}${ages.slice(1)}` : null,
  ]
    .filter(Boolean)
    .join(' ');
  return `${what}, run by ${organisation}.`;
}

/** "Arts and performance in Stanley for ages 4–8, run by X. <first sentence>" */
export function activityMetaDescription(locale: Locale, listing: ActivityListing): string {
  const lead = metaLead(locale, listing);
  const sentence = firstSentence(listingDescription(locale, listing));
  const separator = locale === 'zh-HK' ? '' : ' ';
  return truncate(sentence ? `${lead}${separator}${sentence}` : lead, META_DESCRIPTION_MAX_LENGTH);
}

function absolute(siteOrigin: string, href: string): string {
  return new URL(href, siteOrigin).toString();
}

export function breadcrumbStructuredData(
  siteOrigin: string,
  items: readonly ActivityBreadcrumbItem[],
  current: { readonly label: string; readonly href: string },
): Record<string, unknown> {
  const trail = [...items, current];
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: trail.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.label,
      item: absolute(siteOrigin, item.href),
    })),
  };
}

const IN_LANGUAGE: Readonly<Record<string, string>> = {
  en: 'en',
  zh: 'zh-HK',
  yue: 'zh-HK',
  'zh-HK': 'zh-HK',
};

/** Kinds that are somewhere to go rather than a course, with their schema.org type. */
const VENUE_TYPES: Readonly<Partial<Record<ActivityListing['activity']['kind'], string>>> = {
  place: 'TouristAttraction',
  eat: 'Restaurant',
  preschool: 'Preschool',
};

function venueStructuredData(
  locale: Locale,
  listing: ActivityListing,
  imageUrls: readonly string[],
  pageUrl?: string,
): Record<string, unknown> {
  const description = listingDescription(locale, listing);
  const venue = listing.location;
  return {
    '@context': 'https://schema.org',
    '@type': VENUE_TYPES[listing.activity.kind],
    name: listingTitle(locale, listing),
    ...(pageUrl ? { url: pageUrl } : {}),
    description: description || undefined,
    ...(imageUrls.length > 0 ? { image: imageUrls.slice(0, 5) } : {}),
    ...(venue.address ? { address: venue.address } : {}),
    ...(venue.lat !== null && venue.lng !== null
      ? { geo: { '@type': 'GeoCoordinates', latitude: venue.lat, longitude: venue.lng } }
      : {}),
    ...(listing.activity.kind === 'place' && listing.pricing?.pricingType === 'free'
      ? { isAccessibleForFree: true }
      : {}),
  };
}

export function activityStructuredData(
  locale: Locale,
  listing: ActivityListing,
  imageUrls: readonly string[],
  pageUrl?: string,
): Record<string, unknown> {
  const description = listingDescription(locale, listing);
  const { ageMin, ageMax } = listing.activity;
  const venues = listingVenues(listing);
  const languages = [
    ...new Set(
      venues
        .flatMap((variant) => variant.schedule?.languages ?? [])
        .map((language) => IN_LANGUAGE[language] ?? language),
    ),
  ];
  const category = categoryLabelForListing(locale, listing);
  if (VENUE_TYPES[listing.activity.kind]) {
    return venueStructuredData(locale, listing, imageUrls, pageUrl);
  }
  return {
    '@context': 'https://schema.org',
    '@type': 'Course',
    name: listingTitle(locale, listing),
    ...(pageUrl ? { url: pageUrl } : {}),
    description: description || undefined,
    ...(category ? { about: category } : {}),
    provider: { '@type': 'Organization', name: listingOrgName(locale, listing) },
    ...(imageUrls.length > 0 ? { image: imageUrls.slice(0, 5) } : {}),
    ...(languages.length > 0 ? { inLanguage: languages } : {}),
    ...((ageMin !== null || ageMax !== null) && !isCatchAllAgeRange(ageMin, ageMax)
      ? {
          audience: {
            '@type': 'PeopleAudience',
            ...(ageMin !== null ? { suggestedMinAge: ageMin } : {}),
            ...(ageMax !== null ? { suggestedMaxAge: ageMax } : {}),
          },
        }
      : {}),
    hasCourseInstance: venues.map((variant) => ({
      '@type': 'CourseInstance',
      courseMode: 'onsite',
      location: {
        '@type': 'Place',
        name: variant.location.name ?? placeLabelForLocation(locale, variant.location) ?? undefined,
        ...(variant.location.address ? { address: variant.location.address } : {}),
        ...(variant.location.lat !== null && variant.location.lng !== null
          ? {
              geo: {
                '@type': 'GeoCoordinates',
                latitude: variant.location.lat,
                longitude: variant.location.lng,
              },
            }
          : {}),
      },
    })),
    ...(listing.pricing
      ? {
          offers: {
            '@type': 'Offer',
            price: listing.pricing.amount,
            priceCurrency: listing.pricing.currency.toUpperCase(),
            ...(pageUrl ? { url: pageUrl } : {}),
          },
        }
      : {}),
  };
}

/** JSON for an inline `<script type="application/ld+json">` text child. */
export function serializeJsonLd(value: unknown): string {
  return JSON.stringify(value).replaceAll('<', '\\u003c');
}
