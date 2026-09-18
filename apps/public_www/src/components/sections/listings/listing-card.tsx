'use client';

import Link from 'next/link';

import type { Locale } from '@/content';
import { getContent } from '@/content';
import type { ActivityListing } from '@/lib/activities/types';
import { regionIdForListing } from '@/lib/activities/map-search-url';
import {
  formatListingPrice,
  formatScheduleSnippet,
  listingImageUrl,
  isTemporarilyClosed,
  listingOrgName,
  listingTitle,
  regionLabelForListing,
} from '@/lib/activities/listing-utils';
import { useSearchContext } from '@/components/shared/search/search-context';
import { RegionMapLink } from '@/components/shared/search/region-map-link';
import { ListingCardMiniMap } from '@/components/sections/listings/listing-card-mini-map';
import {
  LISTING_IMAGE_HEIGHT,
  LISTING_IMAGE_WIDTH,
} from '@/lib/listing-image';
import { localizePath } from '@/lib/locale-routing';

interface ListingCardProps {
  readonly locale: Locale;
  readonly listing: ActivityListing;
  readonly parentVerifiedLabel: string;
  readonly freeTrialLabel: string;
  readonly imageAltFallback: string;
  readonly mapAltLabel: string;
  readonly layout?: 'carousel' | 'grid';
  readonly imageLoading?: 'lazy' | 'eager';
  readonly imageFetchPriority?: 'high' | 'low';
  readonly deferRendering?: boolean;
}

export function ListingCard({
  locale,
  listing,
  parentVerifiedLabel,
  freeTrialLabel,
  imageAltFallback,
  mapAltLabel,
  layout = 'carousel',
  imageLoading = 'lazy',
  imageFetchPriority,
  deferRendering = false,
}: ListingCardProps) {
  const { filters } = useSearchContext();
  const widthClassName =
    layout === 'grid' ? 'w-full' : 'w-[280px] shrink-0 sm:w-[300px]';
  const deferClassName = deferRendering ? 'listing-card-deferred' : '';
  const href = `${localizePath('/activity', locale)}?id=${listing.activity.id}`;
  const imageUrl = listingImageUrl(listing);
  const title = listingTitle(locale, listing);
  const orgName = listingOrgName(locale, listing);
  const region = regionLabelForListing(locale, listing);
  const regionId = regionIdForListing(listing);
  const schedule = formatScheduleSnippet(locale, listing.schedule.weeklyEntries);
  const price = formatListingPrice(locale, listing);
  const closedLabel = getContent(locale).searchPage.temporarilyClosedLabel;

  return (
    <article
      className={`listing-card ${widthClassName} ${deferClassName}`.trim()}
    >
      <Link href={href} className="link-unadorned group block">
        <div className="relative aspect-[4/3] overflow-hidden rounded-xl bg-brand-100">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={title}
              width={LISTING_IMAGE_WIDTH}
              height={LISTING_IMAGE_HEIGHT}
              loading={imageLoading}
              decoding="async"
              {...(imageFetchPriority
                ? { fetchPriority: imageFetchPriority }
                : {})}
              className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
            />
          ) : (
            <div className="flex h-full items-center justify-center px-4 text-center text-sm text-ink-500">
              {imageAltFallback}
            </div>
          )}
          <span className="absolute left-3 top-3 flex flex-wrap gap-1.5">
            <span className="flex items-center gap-1 rounded-md bg-white px-2 py-1 text-xs font-semibold text-ink-900 shadow-sm">
              <img
                src="/images/brand/parent-verified.svg"
                alt=""
                width={14}
                height={14}
                aria-hidden="true"
              />
              {parentVerifiedLabel}
            </span>
            {listing.pricing.freeTrialClassOffered ? (
              <span className="rounded-md bg-white px-2 py-1 text-xs font-semibold text-ink-900 shadow-sm">
                {freeTrialLabel}
              </span>
            ) : null}
            {isTemporarilyClosed(listing) ? (
              <span className="rounded-md bg-amber-100 px-2 py-1 text-xs font-semibold text-ink-900 shadow-sm">
                {closedLabel}
              </span>
            ) : null}
          </span>
          <ListingCardMiniMap
            locale={locale}
            listing={listing}
            mapAltLabel={mapAltLabel}
          />
        </div>
        <div className="mt-3 space-y-1">
          <h3 className="line-clamp-2 text-[15px] font-semibold text-ink-900">
            {title}
          </h3>
          <p className="text-sm text-ink-500">
            {orgName}
            {orgName && (region || schedule) ? ' · ' : ''}
            {region && regionId ? (
              <RegionMapLink
                locale={locale}
                label={region}
                filters={filters}
                regionId={regionId}
              />
            ) : (
              region
            )}
            {schedule ? ` · ${schedule}` : ''}
          </p>
          <p className="text-sm font-semibold text-ink-900">
            <span>{price}</span>
          </p>
        </div>
      </Link>
    </article>
  );
}
