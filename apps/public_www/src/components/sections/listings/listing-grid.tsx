'use client';

import type { Locale } from '@/content/locales';
import type { ActivityListing } from '@/lib/activities/types';
import { shouldDeferListingCardRender } from '@/lib/listing-image';

import { ListingCard, type ListingCardLabels } from './listing-card';
import { ListingCardSkeleton } from './listing-card-skeleton';

interface ListingGridProps {
  readonly locale: Locale;
  readonly listings: readonly ActivityListing[];
  readonly isLoading: boolean;
  readonly labels: ListingCardLabels & { readonly empty: string };
}

/**
 * Row cards on phones, then 3 columns from iPad portrait and landscape
 * phones, and 4 on wide screens.
 */
const GRID_CLASS_NAME =
  'listing-grid grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-6 xl:grid-cols-4';

export function ListingGrid({
  locale,
  listings,
  isLoading,
  labels,
}: ListingGridProps) {
  if (isLoading) {
    return (
      <div className={GRID_CLASS_NAME}>
        {Array.from({ length: 8 }).map((_, index) => (
          <ListingCardSkeleton key={`grid-skeleton-${index}`} layout="grid" />
        ))}
      </div>
    );
  }

  if (listings.length === 0) {
    return (
      <p className="rounded-xl border border-brand-100 bg-brand-50 px-4 py-8 text-center text-ink-700">
        {labels.empty}
      </p>
    );
  }

  return (
    <div className={GRID_CLASS_NAME}>
      {listings.map((listing, cardIndex) => (
        <ListingCard
          key={listing.activity.id}
          locale={locale}
          listing={listing}
          layout="grid"
          labels={labels}
          deferRendering={shouldDeferListingCardRender(cardIndex)}
        />
      ))}
    </div>
  );
}
