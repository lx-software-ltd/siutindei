import type { Locale } from '@/content/locales';

import { listingVariants } from './group-listings';
import type { ActivityListing, SearchPricing } from './types';

const SUFFIXES: Record<string, { readonly en: string; readonly zh: string }> = {
  per_class: { en: ' / class', zh: ' / 堂' },
  per_sessions: { en: ' / term', zh: ' / 期' },
  per_hour: { en: ' / hr', zh: ' / 小時' },
  per_day: { en: ' / day', zh: ' / 天' },
  per_month: { en: ' / month', zh: ' / 月' },
  per_year: { en: ' / year', zh: ' / 年' },
};

export function formatMoney(
  locale: Locale,
  amount: number,
  currency: string,
): string {
  return new Intl.NumberFormat(locale === 'zh-HK' ? 'zh-HK' : 'en-HK', {
    style: 'currency',
    currency: currency.toUpperCase(),
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Price of one class, the same rule the search API sorts and filters by. */
export function classPriceEquivalent(pricing: SearchPricing | null): number | null {
  if (!pricing) {
    return null;
  }
  switch (pricing.pricingType) {
    case 'free':
      return 0;
    case 'per_class':
    case 'per_hour':
      return pricing.amount;
    case 'per_sessions':
      return pricing.sessionsCount && pricing.sessionsCount > 0
        ? pricing.amount / pricing.sessionsCount
        : null;
    default:
      return null;
  }
}

export function formatPricing(locale: Locale, pricing: SearchPricing): string {
  if (pricing.pricingType === 'free') {
    return locale === 'zh-HK' ? '免費' : 'Free';
  }
  const amount = formatMoney(locale, pricing.amount, pricing.currency);
  if (
    pricing.pricingType === 'per_sessions' &&
    pricing.sessionsCount &&
    pricing.sessionsCount > 0
  ) {
    return locale === 'zh-HK'
      ? `${amount} / ${pricing.sessionsCount}堂`
      : `${amount} / ${pricing.sessionsCount} classes`;
  }
  const suffix = SUFFIXES[pricing.pricingType];
  if (!suffix) {
    return amount;
  }
  return `${amount}${locale === 'zh-HK' ? suffix.zh : suffix.en}`;
}

/** "HK$200 per class" for a term price, or null when it adds nothing. */
export function formatClassEquivalent(
  locale: Locale,
  pricing: SearchPricing,
): string | null {
  if (pricing.pricingType !== 'per_sessions') {
    return null;
  }
  const perClass = classPriceEquivalent(pricing);
  if (perClass === null) {
    return null;
  }
  const amount = formatMoney(locale, Math.round(perClass), pricing.currency);
  return locale === 'zh-HK' ? `約每堂 ${amount}` : `About ${amount} per class`;
}

function pricingKey(pricing: SearchPricing): string {
  return `${pricing.pricingType}:${pricing.amount}:${pricing.currency}:${pricing.sessionsCount ?? ''}`;
}

/** Distinct prices across the rows of a listing, cheapest per class first. */
export function listingPrices(listing: ActivityListing): readonly SearchPricing[] {
  const byKey = new Map<string, SearchPricing>();
  for (const variant of listingVariants(listing)) {
    if (variant.pricing && !byKey.has(pricingKey(variant.pricing))) {
      byKey.set(pricingKey(variant.pricing), variant.pricing);
    }
  }
  return [...byKey.values()].sort((left, right) => {
    const leftValue = classPriceEquivalent(left) ?? Number.POSITIVE_INFINITY;
    const rightValue = classPriceEquivalent(right) ?? Number.POSITIVE_INFINITY;
    return leftValue - rightValue;
  });
}

/** One price line for a card: the price, or "From ..." when rows differ. */
export function formatListingPriceSummary(
  locale: Locale,
  listing: ActivityListing,
): string | null {
  const prices = listingPrices(listing);
  const cheapest = prices[0];
  if (!cheapest) {
    return null;
  }
  const text = formatPricing(locale, cheapest);
  if (prices.length === 1) {
    return text;
  }
  return locale === 'zh-HK' ? `${text} 起` : `From ${text}`;
}
