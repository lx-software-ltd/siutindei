import { formatContentTemplate } from '@/content/content-field-utils';
import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { joinPlaceNames, namedOpenPlace } from '@/lib/home-wizard/area-scope';

import { staticActivityPath } from './activity-href';
import { listingVariants } from './group-listings';
import { listingTitle } from './listing-utils';
import { classPriceEquivalent, formatMoney, listingPrices } from './price-format';
import { dayLabel, toHongKongSession } from './schedule-format';
import type { ActivityListing } from './types';

const HONG_KONG: Readonly<Record<Locale, string>> = { en: 'Hong Kong', 'zh-HK': '香港' };

export interface ScopePlace {
  /** "Stanley", or "Hong Kong" when the scope is not one named place. */
  readonly place: string;
  /** "Stanley, Hong Kong" / "香港赤柱". */
  readonly placeFull: string;
}

export function catalogueScopePlace(
  locale: Locale,
  copy: SiteContent['discovery'],
): ScopePlace {
  const named = namedOpenPlace(locale);
  const hongKong = HONG_KONG[locale];
  if (named.kind !== 'named') {
    return { place: hongKong, placeFull: hongKong };
  }
  const place = joinPlaceNames(named.names, {
    comma: copy.placeListComma,
    pairTemplate: copy.placePairTemplate,
    finalTemplate: copy.placeFinalTemplate,
  });
  return { place, placeFull: locale === 'zh-HK' ? `${hongKong}${place}` : `${place}, ${hongKong}` };
}

export function lowerCategory(locale: Locale, label: string): string {
  return locale === 'en' ? label.charAt(0).toLowerCase() + label.slice(1) : label;
}

export interface LandingFacts {
  readonly ages: string | null;
  readonly days: string | null;
  readonly prices: string | null;
}

/** Ages, weekdays, and per-class prices across the listings, from their data. */
export function landingFacts(
  locale: Locale,
  listings: readonly ActivityListing[],
  copy: SiteContent['activitiesPage'],
): LandingFacts {
  const minimums = listings.map((listing) => listing.activity.ageMin).filter((age) => age !== null);
  const maximums = listings.map((listing) => listing.activity.ageMax).filter((age) => age !== null);
  const ages =
    minimums.length > 0 && maximums.length > 0
      ? formatContentTemplate(copy.agesRangeTemplate, {
          min: Math.min(...minimums),
          max: Math.max(...maximums),
        })
      : null;

  const days = new Set<number>();
  for (const listing of listings) {
    for (const variant of listingVariants(listing)) {
      for (const entry of variant.schedule?.weeklyEntries ?? []) {
        days.add(toHongKongSession(entry).day);
      }
    }
  }
  const dayList = [...days]
    .sort((left, right) => ((left + 6) % 7) - ((right + 6) % 7))
    .map((day) => dayLabel(locale, day, 'long'))
    .join(locale === 'zh-HK' ? '、' : ', ');

  const prices = listings
    .flatMap((listing) => listingPrices(listing))
    .map((pricing) => ({ value: classPriceEquivalent(pricing), currency: pricing.currency }))
    .filter((price): price is { value: number; currency: string } => price.value !== null);
  const currency = prices[0]?.currency;
  const sameCurrency = prices.filter((price) => price.currency === currency);
  let priceRange: string | null = null;
  if (currency && sameCurrency.length > 0) {
    const low = Math.min(...sameCurrency.map((price) => price.value));
    const high = Math.max(...sameCurrency.map((price) => price.value));
    priceRange =
      low === high
        ? formatMoney(locale, low, currency)
        : formatContentTemplate(copy.priceRangeTemplate, {
            min: formatMoney(locale, low, currency),
            max: formatMoney(locale, high, currency),
          });
  }

  return { ages, days: dayList || null, prices: priceRange };
}

export function itemListStructuredData(
  siteOrigin: string,
  locale: Locale,
  name: string,
  listings: readonly ActivityListing[],
): Record<string, unknown> {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name,
    numberOfItems: listings.length,
    itemListElement: listings.map((listing, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: listingTitle(locale, listing),
      url: new URL(staticActivityPath(locale, listing.activity.id), siteOrigin).toString(),
    })),
  };
}
