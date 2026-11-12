import type { Locale } from '@/content/locales';
import { formatClassEquivalent, formatPricing } from '@/lib/activities/price-format';
import type { SearchPricing } from '@/lib/activities/types';

import { DetailSection } from './detail-section';
import type { ActivityDetailCopy } from './types';

export function ActivityPrice({
  locale,
  pricings,
  hasFreeTrial,
  copy,
}: {
  readonly locale: Locale;
  readonly pricings: readonly SearchPricing[];
  readonly hasFreeTrial: boolean;
  readonly copy: ActivityDetailCopy;
}) {
  return (
    <DetailSection id="price" title={copy.priceHeading}>
      {pricings.length === 0 ? (
        <p className="text-sm text-ink-500">{copy.priceMissingLabel}</p>
      ) : (
        <ul className="space-y-2">
          {pricings.map((pricing) => {
            const equivalent = formatClassEquivalent(locale, pricing);
            return (
              <li key={JSON.stringify(pricing)}>
                <p className="text-lg font-semibold text-ink-900">
                  {formatPricing(locale, pricing)}
                </p>
                {equivalent ? <p className="text-sm text-ink-500">{equivalent}</p> : null}
              </li>
            );
          })}
        </ul>
      )}
      {hasFreeTrial ? (
        <p className="mt-3 inline-flex rounded-md bg-brand-100 px-2.5 py-1 text-sm font-semibold text-ink-900">
          {copy.freeTrialLabel}
        </p>
      ) : null}
    </DetailSection>
  );
}
