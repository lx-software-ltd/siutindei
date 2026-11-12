'use client';

import { useEffect, useRef, useState } from 'react';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { ActivityGoogleMap } from '@/components/shared/maps/activity-google-map';
import { isGoogleMapsEnabled } from '@/lib/google-maps/config';
import { listingsWithCoordinates } from '@/lib/google-maps/coordinates';
import type { ActivityListing } from '@/lib/activities/types';

import { SearchMapListItem, type SearchMapListItemLabels } from './search-map-list-item';

/** The phone layout in globals.css where the map fills a page that does not scroll. */
const PHONE_MAP_QUERY =
  '(max-width: 767px) and (min-height: 501px), (max-width: 767px) and (orientation: portrait)';

const ENLARGE_ICON_SRC = '/images/ui/enlarge-map.svg';
const REDUCE_ICON_SRC = '/images/ui/reduce-map.svg';

export interface SearchMapLoadMore {
  readonly hasMore: boolean;
  readonly isLoadingMore: boolean;
  readonly errorMessage: string | null;
  readonly onLoadMore: () => void;
}

interface SearchMapSplitLayoutProps {
  readonly locale: Locale;
  readonly copy: SiteContent['searchPage'];
  readonly listings: readonly ActivityListing[];
  readonly selectedId: string | null;
  readonly onSelect: (activityId: string) => void;
  readonly isLoading: boolean;
  readonly loadMore?: SearchMapLoadMore;
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
    <div className="relative isolate h-full w-full">
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
          groupLabel={copy.mapPinGroupLabel}
          oneFingerPanQuery={PHONE_MAP_QUERY}
        />
      ) : null}
    </div>
  );
}

function LoadMoreButton({
  loadMore,
  label,
  className = '',
}: {
  readonly loadMore: SearchMapLoadMore;
  readonly label: string;
  readonly className?: string;
}) {
  return (
    <div className={`flex flex-col items-center justify-center gap-2 ${className}`}>
      {loadMore.errorMessage ? (
        <p className="text-center text-sm text-red-700">{loadMore.errorMessage}</p>
      ) : null}
      <button
        type="button"
        onClick={loadMore.onLoadMore}
        disabled={loadMore.isLoadingMore}
        className="min-h-11 rounded-full bg-brand-500 px-6 text-sm font-semibold text-ink-900 hover:bg-brand-600 disabled:opacity-60"
      >
        {label}
      </button>
    </div>
  );
}

const CARD_SETTLE_MS = 120;

function centredCardId(track: HTMLElement): string | null {
  const centre = track.scrollLeft + track.clientWidth / 2;
  let nearestId: string | null = null;
  let nearestDistance = Number.POSITIVE_INFINITY;
  for (const card of track.querySelectorAll<HTMLElement>('[data-activity-id]')) {
    const distance = Math.abs(card.offsetLeft + card.clientWidth / 2 - centre);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestId = card.dataset.activityId ?? null;
    }
  }
  return nearestId;
}

/**
 * Phones: a swipeable row of cards over the map. A tapped pin brings its
 * card to the centre, a swipe selects the pin of the card it lands on, and
 * a tap on a card opens the activity.
 */
function MapCardSheet({
  locale,
  listings,
  selectedId,
  onSelect,
  labels,
  loadMore,
  loadMoreLabel,
  ariaLabel,
}: {
  readonly locale: Locale;
  readonly listings: readonly ActivityListing[];
  readonly selectedId: string | null;
  readonly onSelect: (activityId: string) => void;
  readonly labels: SearchMapListItemLabels;
  readonly loadMore?: SearchMapLoadMore;
  readonly loadMoreLabel: string;
  readonly ariaLabel: string;
}) {
  const trackRef = useRef<HTMLUListElement>(null);
  const selectedIdRef = useRef(selectedId);
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    selectedIdRef.current = selectedId;
    onSelectRef.current = onSelect;
  }, [onSelect, selectedId]);

  useEffect(() => {
    const track = trackRef.current;
    if (!track || !selectedId) {
      return;
    }
    const card = track.querySelector<HTMLElement>(`[data-activity-id="${CSS.escape(selectedId)}"]`);
    if (!card || typeof track.scrollTo !== 'function') {
      return;
    }
    // A swipe that selected this card already left it centred.
    if (centredCardId(track) === selectedId) {
      return;
    }
    track.scrollTo({
      left: card.offsetLeft - (track.clientWidth - card.clientWidth) / 2,
      behavior: 'smooth',
    });
  }, [selectedId]);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) {
      return;
    }
    let settleTimer: number | undefined;
    // Waiting for the scroll to rest keeps a pin-driven scroll from
    // selecting the cards it passes.
    function handleScroll() {
      window.clearTimeout(settleTimer);
      settleTimer = window.setTimeout(() => {
        if (!track || track.clientWidth === 0) {
          return;
        }
        const id = centredCardId(track);
        if (id && id !== selectedIdRef.current) {
          onSelectRef.current(id);
        }
      }, CARD_SETTLE_MS);
    }
    track.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      window.clearTimeout(settleTimer);
      track.removeEventListener('scroll', handleScroll);
    };
  }, []);

  return (
    <div className="search-map-split-layout__sheet absolute inset-x-0 bottom-3 z-20">
      <ul
        ref={trackRef}
        aria-label={ariaLabel}
        className="listing-carousel__track flex snap-x snap-mandatory gap-2 overflow-x-auto px-4 pb-1"
      >
        {listings.map((listing) => (
          <li
            key={listing.activity.id}
            data-activity-id={listing.activity.id}
            className="w-[86%] max-w-sm shrink-0 snap-center"
          >
            <SearchMapListItem
              kind="summary"
              compact
              locale={locale}
              listing={listing}
              isSelected={selectedId === listing.activity.id}
              labels={labels}
              className="h-full"
            />
          </li>
        ))}
        {loadMore?.hasMore ? (
          <li className="flex w-40 shrink-0 snap-center items-center">
            <LoadMoreButton loadMore={loadMore} label={loadMoreLabel} className="w-full" />
          </li>
        ) : null}
      </ul>
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
  loadMore,
}: SearchMapSplitLayoutProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const mappableCount = listingsWithCoordinates(listings).length;
  const mapsEnabled = isGoogleMapsEnabled();
  const selectedListing =
    listings.find((listing) => listing.activity.id === selectedId) ?? null;
  const showMapCards = !isLoading && listings.length > 0 && mappableCount > 0;
  const labels: SearchMapListItemLabels = {
    imageFallback: copy.imageFallbackLabel,
    view: copy.viewLabel,
    locationsCount: copy.locationsCountLabel,
    detailsOnRequest: copy.detailsOnRequestLabel,
  };

  if (!mapsEnabled) {
    return (
      <p className="rounded-xl border border-brand-100 bg-brand-50 px-4 py-8 text-center text-ink-700">
        {copy.mapUnavailableLabel}
      </p>
    );
  }

  const layoutClassName = isExpanded
    ? 'search-map-split-layout search-map-split-layout--expanded'
    : 'search-map-split-layout';
  const summaryCardClassName = isExpanded
    ? 'search-map-split-layout__card absolute bottom-4 left-4 z-20 hidden w-[min(24rem,calc(100%-2rem))] md:block short:hidden'
    : 'search-map-split-layout__card absolute bottom-4 left-4 z-20 hidden w-[min(24rem,calc(100%-2rem))] md:block lg:hidden short:hidden';

  return (
    <div className={layoutClassName} data-hide-whatsapp-fab>
      <section
        aria-label={copy.resultsLabel}
        className="search-map-split-layout__list border-brand-100 px-4 py-4 sm:px-6 lg:px-4"
      >
        {isLoading ? (
          <p className="text-center text-sm text-ink-500">{copy.loadingMapLabel}</p>
        ) : null}
        {!isLoading && listings.length === 0 ? (
          <p className="text-center text-sm text-ink-700">{copy.emptyLabel}</p>
        ) : null}
        {!isLoading && listings.length > 0 && mappableCount === 0 ? (
          <p className="text-center text-sm text-ink-700">{copy.mapEmptyLabel}</p>
        ) : null}
        <ul className="search-map-split-layout__list-items gap-3">
          {listings.map((listing) => (
            <li key={listing.activity.id}>
              <SearchMapListItem
                kind="select"
                locale={locale}
                listing={listing}
                isSelected={selectedId === listing.activity.id}
                labels={labels}
                onSelect={() => onSelect(listing.activity.id)}
                className="h-full"
              />
            </li>
          ))}
        </ul>
        {loadMore?.hasMore ? (
          <LoadMoreButton loadMore={loadMore} label={copy.loadMoreLabel} className="py-6" />
        ) : null}
      </section>
      <div className="search-map-split-layout__map relative">
        <button
          type="button"
          aria-label={isExpanded ? copy.reduceMapLabel : copy.enlargeMapLabel}
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
        {showMapCards ? (
          <MapCardSheet
            locale={locale}
            listings={listings}
            selectedId={selectedId}
            onSelect={onSelect}
            labels={labels}
            loadMore={loadMore}
            loadMoreLabel={copy.loadMoreLabel}
            ariaLabel={copy.resultsLabel}
          />
        ) : null}
        {showMapCards && selectedListing ? (
          <div className={summaryCardClassName}>
            <SearchMapListItem
              kind="summary"
              locale={locale}
              listing={selectedListing}
              labels={labels}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
