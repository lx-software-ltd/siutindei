'use client';

import { useState } from 'react';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { ActivityGoogleMap } from '@/components/shared/maps/activity-google-map';
import { isGoogleMapsEnabled } from '@/lib/google-maps/config';
import { listingsWithCoordinates } from '@/lib/google-maps/coordinates';
import type { ActivityListing } from '@/lib/activities/types';

import { SearchMapListItem } from './search-map-list-item';

const ENLARGE_ICON_SRC = '/images/ui/enlarge-map.svg';
const REDUCE_ICON_SRC = '/images/ui/reduce-map.svg';

interface SearchMapSplitLayoutProps {
  readonly locale: Locale;
  readonly copy: SiteContent['searchPage'];
  readonly listings: readonly ActivityListing[];
  readonly selectedId: string | null;
  readonly onSelect: (activityId: string) => void;
  readonly isLoading: boolean;
}

interface MapPaneBodyProps {
  readonly locale: Locale;
  readonly copy: SiteContent['searchPage'];
  readonly listings: readonly ActivityListing[];
  readonly selectedId: string | null;
  readonly onSelect: (activityId: string) => void;
  readonly isLoading: boolean;
  readonly mappableCount: number;
}

function MapPaneBody({
  locale,
  copy,
  listings,
  selectedId,
  onSelect,
  isLoading,
  mappableCount,
}: MapPaneBodyProps) {
  const canRenderMap = isLoading || mappableCount > 0;

  return (
    <div className="relative h-full w-full">
      {isLoading ? (
        <p className="absolute inset-0 z-10 flex items-center justify-center bg-brand-50 px-4 text-center text-sm text-ink-500">
          {copy.loadingMapLabel}
        </p>
      ) : null}
      {!isLoading && listings.length === 0 ? (
        <p className="flex h-full items-center justify-center bg-brand-50 px-4 text-center text-sm text-ink-700">
          {copy.emptyLabel}
        </p>
      ) : null}
      {!isLoading && listings.length > 0 && mappableCount === 0 ? (
        <div className="flex h-full items-center justify-center bg-brand-50 px-4 text-center text-sm text-ink-500">
          {copy.mapEmptyLabel}
        </div>
      ) : null}
      {canRenderMap ? (
        <ActivityGoogleMap
          locale={locale}
          listings={listings}
          selectedId={selectedId}
          onSelect={onSelect}
          className="h-full w-full"
          ariaLabel={copy.mapAriaLabel}
        />
      ) : null}
    </div>
  );
}

export function SearchMapSplitLayout({
  locale,
  copy,
  listings,
  selectedId,
  onSelect,
  isLoading,
}: SearchMapSplitLayoutProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const mappableCount = listingsWithCoordinates(listings).length;
  const mapsEnabled = isGoogleMapsEnabled();
  const selectedListing =
    listings.find((listing) => listing.activity.id === selectedId) ?? null;
  const showOverlayCard =
    !isLoading && selectedListing !== null && mappableCount > 0;

  if (!mapsEnabled) {
    return (
      <p className="rounded-xl border border-brand-100 bg-brand-50 px-4 py-8 text-center text-ink-700">
        {copy.mapUnavailableLabel}
      </p>
    );
  }

  const layoutClassName = isExpanded
    ? 'search-map-split-layout search-map-split-layout--expanded'
    : 'search-map-split-layout lg:grid lg:grid-cols-2 lg:gap-0';
  const mapHeightClassName = isExpanded
    ? 'h-[calc(100dvh-10rem)]'
    : 'h-[calc(100dvh-10rem)] lg:h-[calc(100vh-12rem)]';
  const overlayCardClassName = isExpanded
    ? 'search-map-split-layout__card absolute inset-x-0 bottom-20 z-20 px-4'
    : 'search-map-split-layout__card absolute inset-x-0 bottom-20 z-20 px-4 lg:hidden';

  return (
    <div className={layoutClassName}>
      {!isExpanded ? (
        <div className="search-map-split-layout__list hidden max-h-[calc(100vh-12rem)] overflow-y-auto border-b border-brand-100 px-4 py-4 lg:block lg:border-b-0 lg:border-r">
          {isLoading ? (
            <p className="text-center text-sm text-ink-500">
              {copy.loadingMapLabel}
            </p>
          ) : null}
          {!isLoading && listings.length === 0 ? (
            <p className="text-center text-sm text-ink-700">{copy.emptyLabel}</p>
          ) : null}
          {!isLoading && listings.length > 0 && mappableCount === 0 ? (
            <p className="text-center text-sm text-ink-700">
              {copy.mapEmptyLabel}
            </p>
          ) : null}
          <ul className="space-y-3">
            {listings.map((listing) => (
              <li key={listing.activity.id}>
                <SearchMapListItem
                  kind="select"
                  locale={locale}
                  listing={listing}
                  isSelected={selectedId === listing.activity.id}
                  imageFallbackLabel={copy.imageFallbackLabel}
                  onSelect={() => onSelect(listing.activity.id)}
                />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div
        className={`search-map-split-layout__map relative ${mapHeightClassName}`}
      >
        <button
          type="button"
          aria-label={
            isExpanded ? copy.reduceMapLabel : copy.enlargeMapLabel
          }
          onClick={() => setIsExpanded((current) => !current)}
          className={
            'search-map-size-toggle absolute right-3 top-3 z-20 hidden ' +
            'lg:inline-flex h-11 items-center gap-2 rounded-full border ' +
            'border-ink-900/15 bg-white px-3 text-sm font-semibold ' +
            'text-ink-900 shadow-lg transition hover:bg-brand-50'
          }
        >
          <img
            src={isExpanded ? REDUCE_ICON_SRC : ENLARGE_ICON_SRC}
            alt=""
            width={16}
            height={16}
            decoding="async"
            aria-hidden="true"
            className="h-4 w-4"
          />
          {isExpanded ? copy.reduceMapLabel : copy.enlargeMapLabel}
        </button>
        <MapPaneBody
          locale={locale}
          copy={copy}
          listings={listings}
          selectedId={selectedId}
          onSelect={onSelect}
          isLoading={isLoading}
          mappableCount={mappableCount}
        />
        {showOverlayCard && selectedListing ? (
          <div className={overlayCardClassName}>
            <SearchMapListItem
              kind="summary"
              locale={locale}
              listing={selectedListing}
              imageFallbackLabel={copy.imageFallbackLabel}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
