'use client';

import type { Locale } from '@/content/locales';
import type { ActivityListing } from '@/lib/activities/types';
import { shouldDeferListingCardRender } from '@/lib/listing-image';

import { ListingCard } from './listing-card';
import { ListingCardSkeleton } from './listing-card-skeleton';

interface ListingGridProps {
  readonly locale: Locale;
  readonly listings: readonly ActivityListing[];
  readonly isLoading: boolean;
  readonly labels: {
    readonly parentVerified: string;
    readonly freeTrial: string;
    readonly imageFallback: string;
    readonly empty: string;
    readonly mapAlt: string;
  };
}

export function ListingGrid({
  locale,
  listings,
  isLoading,
  labels,
}: ListingGridProps) {
  if (isLoading) {
    return (
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <ListingCardSkeleton key={`grid-skeleton-${index}`} />
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
    <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {listings.map((listing, cardIndex) => (
        <ListingCard
          key={listing.activity.id}
          locale={locale}
          listing={listing}
          layout="grid"
          parentVerifiedLabel={labels.parentVerified}
          freeTrialLabel={labels.freeTrial}
          imageAltFallback={labels.imageFallback}
          mapAltLabel={labels.mapAlt}
          deferRendering={shouldDeferListingCardRender(cardIndex)}
          showMiniMap={cardIndex < 6}
        />
      ))}
    </div>
  );
}
