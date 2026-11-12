'use client';

import Link from 'next/link';
import { useState } from 'react';

import type { Locale } from '@/content/locales';
import { useChromeCopy } from '@/components/shared/chrome-copy';
import { useSearchContext } from '@/components/shared/search/search-context';
import { RegionMapLink } from '@/components/shared/search/region-map-link';
import { ListingCardMiniMap } from '@/components/sections/listings/listing-card-mini-map';
import { listingVariants, listingVenues } from '@/lib/activities/group-listings';
import {
  categoryLabelForListing,
  listingAgeLabel,
  shortPlaceLabel,
} from '@/lib/activities/listing-facts';
import {
  formatScheduleSnippet,
  isTemporarilyClosed,
  listingImageIsLogo,
  listingImageUrl,
  listingOrgName,
  listingTitle,
} from '@/lib/activities/listing-utils';
import { regionIdForListing } from '@/lib/activities/map-search-url';
import { formatListingPriceSummary } from '@/lib/activities/price-format';
import type { ActivityListing } from '@/lib/activities/types';
import { iconSrcForActivityCategory } from '@/lib/home-wizard/choice-icons';
import { formatTemplate } from '@/lib/format-template';
import { LISTING_IMAGE_HEIGHT, LISTING_IMAGE_WIDTH } from '@/lib/listing-image';
import { localizePath } from '@/lib/locale-routing';

export interface ListingCardLabels {
  readonly parentVerified: string;
  readonly freeTrial: string;
  readonly imageFallback: string;
  readonly mapAlt: string;
  readonly locationsCount: string;
  readonly detailsOnRequest: string;
}

interface ListingCardProps {
  readonly locale: Locale;
  readonly listing: ActivityListing;
  readonly labels: ListingCardLabels;
  /** `grid` becomes a compact row card on phones. */
  readonly layout?: 'carousel' | 'grid';
  readonly imageLoading?: 'lazy' | 'eager';
  readonly imageFetchPriority?: 'high' | 'low';
  readonly deferRendering?: boolean;
  readonly showMiniMap?: boolean;
}

export function listingMetaLine(
  locale: Locale,
  listing: ActivityListing,
  locationsCountLabel: string,
): { readonly place: string | null; readonly schedule: string | null } {
  const venues = listingVenues(listing);
  const place =
    venues.length > 1
      ? formatTemplate(locationsCountLabel, { count: venues.length })
      : shortPlaceLabel(locale, listing.location);
  const entries = listingVariants(listing).flatMap(
    (variant) => variant.schedule?.weeklyEntries ?? [],
  );
  return { place, schedule: formatScheduleSnippet(locale, entries) };
}

export function ListingCard({
  locale,
  listing,
  labels,
  layout = 'carousel',
  imageLoading = 'lazy',
  imageFetchPriority,
  deferRendering = false,
  showMiniMap = false,
}: ListingCardProps) {
  const { filters } = useSearchContext();
  const closedLabel = useChromeCopy(locale).temporarilyClosedLabel;
  const [imageFailed, setImageFailed] = useState(false);
  const isGrid = layout === 'grid';
  const href = `${localizePath('/activity', locale)}?id=${listing.activity.id}`;
  const imageUrl = imageFailed ? null : listingImageUrl(listing);
  const isLogo = listingImageIsLogo(listing);
  const title = listingTitle(locale, listing);
  const orgName = listingOrgName(locale, listing);
  const regionId = regionIdForListing(listing);
  const { place, schedule } = listingMetaLine(locale, listing, labels.locationsCount);
  const price = formatListingPriceSummary(locale, listing);
  const ageLabel = listingAgeLabel(locale, listing);
  const categoryLabel = categoryLabelForListing(locale, listing);
  const hasFreeTrial = listingVariants(listing).some(
    (variant) => variant.pricing?.freeTrialClassOffered,
  );
  const singleVenue = listingVenues(listing).length <= 1;
  const closed = isTemporarilyClosed(listing);

  const articleClassName = isGrid
    ? 'listing-card relative flex w-full gap-3 sm:block'
    : 'listing-card relative w-[280px] shrink-0 sm:w-[300px]';
  const photoClassName = isGrid
    ? 'relative aspect-square w-28 shrink-0 overflow-hidden rounded-xl bg-brand-100 sm:aspect-[4/3] sm:w-full'
    : 'relative aspect-[4/3] overflow-hidden rounded-xl bg-brand-100';

  return (
    <article
      className={`group ${articleClassName} ${deferRendering ? 'listing-card-deferred' : ''}`.trim()}
    >
      <div className={photoClassName}>
        {imageUrl ? (
          <img
            src={imageUrl}
            alt=""
            width={LISTING_IMAGE_WIDTH}
            height={LISTING_IMAGE_HEIGHT}
            loading={imageLoading}
            decoding="async"
            {...(imageFetchPriority ? { fetchPriority: imageFetchPriority } : {})}
            onError={() => setImageFailed(true)}
            className={
              isLogo
                ? 'h-full w-full bg-white object-contain p-4'
                : 'h-full w-full object-cover transition duration-300 group-hover:scale-105'
            }
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-1 px-2 text-center text-xs text-ink-500">
            <img
              src={iconSrcForActivityCategory(listing.activity.categoryId)}
              alt=""
              width={48}
              height={48}
              aria-hidden="true"
              className="h-10 w-10 object-contain opacity-80 sm:h-14 sm:w-14"
            />
            <span className={isGrid ? 'hidden sm:inline' : ''}>{labels.imageFallback}</span>
          </div>
        )}
        {closed || listing.organization.parentVerified ? (
          <span className="absolute left-2 top-2 flex flex-wrap gap-1.5">
            {closed ? (
              <span className="rounded-md bg-amber-100 px-2 py-1 text-xs font-semibold text-ink-900 shadow-sm">
                {closedLabel}
              </span>
            ) : null}
            {listing.organization.parentVerified ? (
              <span className="flex items-center gap-1 rounded-md bg-white px-2 py-1 text-xs font-semibold text-ink-900 shadow-sm">
                <img
                  src="/images/brand/parent-verified.svg"
                  alt=""
                  width={14}
                  height={14}
                  aria-hidden="true"
                />
                <span className={isGrid ? 'sr-only sm:not-sr-only' : ''}>
                  {labels.parentVerified}
                </span>
              </span>
            ) : null}
          </span>
        ) : null}
      </div>
      <div className={isGrid ? 'min-w-0 flex-1 space-y-1 sm:mt-3' : 'mt-3 space-y-1'}>
        {categoryLabel || ageLabel ? (
          <p className="flex flex-wrap gap-1.5">
            {ageLabel ? (
              <span className="rounded-full bg-brand-100 px-2 py-0.5 text-xs font-semibold text-ink-900">
                {ageLabel}
              </span>
            ) : null}
            {categoryLabel ? (
              <span
                className={`rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-ink-700 ${isGrid ? 'hidden sm:inline' : ''}`}
              >
                {categoryLabel}
              </span>
            ) : null}
          </p>
        ) : null}
        <h3 className="line-clamp-2 text-[15px] font-semibold text-ink-900">
          <Link
            href={href}
            className="link-unadorned after:absolute after:inset-0 after:content-['']"
          >
            {title}
          </Link>
        </h3>
        <p className="truncate text-sm text-ink-500">{orgName}</p>
        {place || schedule ? (
          <p className="text-sm text-ink-700">
            {place && singleVenue && regionId ? (
              <RegionMapLink
                locale={locale}
                label={place}
                filters={filters}
                regionId={regionId}
                className="relative z-10"
              />
            ) : (
              place
            )}
            {place && schedule ? ' · ' : ''}
            {schedule}
          </p>
        ) : null}
        {price || hasFreeTrial ? (
          <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-900">
            {price ? <span>{price}</span> : null}
            {hasFreeTrial ? (
              <span className="rounded-md bg-leaf-500/20 px-1.5 py-0.5 text-xs font-semibold text-ink-900">
                {labels.freeTrial}
              </span>
            ) : null}
          </p>
        ) : null}
        {!price && !schedule ? (
          <p className="text-sm text-ink-500">{labels.detailsOnRequest}</p>
        ) : null}
        {showMiniMap ? (
          <ListingCardMiniMap locale={locale} listing={listing} mapAltLabel={labels.mapAlt} />
        ) : null}
      </div>
    </article>
  );
}
