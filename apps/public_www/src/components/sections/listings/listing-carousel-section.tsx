'use client';

import Link from 'next/link';

import type { Locale } from '@/content/locales';
import { Carousel } from '@/components/shared/ui/carousel';
import type { ActivityListing } from '@/lib/activities/types';
import {
  listingCardImageLoading,
  shouldDeferListingSectionRender,
} from '@/lib/listing-image';

import { ListingCard } from './listing-card';
import { ListingCardSkeleton } from './listing-card-skeleton';

const CHEVRON_RIGHT_SRC = '/images/ui/chevron-right.svg';

interface ListingCarouselSectionProps {
  readonly locale: Locale;
  readonly title: string;
  readonly searchHref: string;
  readonly seeAllLabel: string;
  readonly listings: readonly ActivityListing[];
  readonly isLoading: boolean;
  readonly sectionIndex?: number;
  readonly isPrimaryCarousel?: boolean;
  readonly labels: {
    readonly parentVerified: string;
    readonly freeTrial: string;
    readonly imageFallback: string;
    readonly mapAlt: string;
  };
}

export function ListingCarouselSection({
  locale,
  title,
  searchHref,
  seeAllLabel,
  listings,
  isLoading,
  sectionIndex = 0,
  isPrimaryCarousel = false,
  labels,
}: ListingCarouselSectionProps) {
  const sectionClassName = shouldDeferListingSectionRender(sectionIndex)
    ? 'listing-section-deferred py-8'
    : 'py-8';
  const seeAllAriaLabel = `${seeAllLabel}: ${title}`;

  return (
    <section className={sectionClassName} data-section-id="listing-carousel">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-3">
          <h2 className="min-w-0 text-xl font-semibold text-ink-900 sm:text-2xl">
            <Link href={searchHref} className="underline-offset-[0.15em]">
              {title}
            </Link>
          </h2>
          <Link
            href={searchHref}
            aria-label={seeAllAriaLabel}
            className="link-unadorned listing-carousel__nav inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-ink-900/15 bg-white p-0 leading-none text-ink-700 hover:bg-brand-50"
          >
            <img
              src={CHEVRON_RIGHT_SRC}
              alt=""
              width={12}
              height={12}
              decoding="async"
              aria-hidden="true"
              className="listing-carousel__arrow block h-3 w-3"
            />
          </Link>
        </div>
        <div className="mt-4">
          <Carousel ariaLabel={title}>
            {isLoading
              ? Array.from({ length: 4 }).map((_, index) => (
                  <ListingCardSkeleton key={`skeleton-${index}`} />
                ))
              : listings.map((listing, cardIndex) => {
                  const imageProps = listingCardImageLoading({
                    cardIndex,
                    isPrimaryCarousel,
                  });
                  return (
                    <ListingCard
                      key={listing.activity.id}
                      locale={locale}
                      listing={listing}
                      parentVerifiedLabel={labels.parentVerified}
                      freeTrialLabel={labels.freeTrial}
                      imageAltFallback={labels.imageFallback}
                      mapAltLabel={labels.mapAlt}
                      imageLoading={imageProps.imageLoading}
                      imageFetchPriority={imageProps.imageFetchPriority}
                    />
                  );
                })}
          </Carousel>
        </div>
      </div>
    </section>
  );
}
