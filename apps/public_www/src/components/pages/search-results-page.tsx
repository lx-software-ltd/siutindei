'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { FilterChipRow } from '@/components/sections/search/filter-chip-row';
import { SearchMapSplitLayout } from '@/components/sections/search/search-map-split-layout';
import { SearchResultsSummary } from '@/components/sections/search/search-results-summary';
import { SearchViewToggle } from '@/components/sections/search/search-view-toggle';
import { useApplySearchFilters } from '@/components/sections/search/use-apply-search-filters';
import { ListingGrid } from '@/components/sections/listings/listing-grid';
import { useSearchContext } from '@/components/shared/search/search-context';
import { SEARCH_RESULTS_PAGE_LIMIT } from '@/lib/activities/search-limits';
import { buildMapSearchHref, buildSearchPageHref } from '@/lib/activities/map-search-url';
import { rememberSearchHref } from '@/lib/activities/recent-storage';
import { useActivitySearch } from '@/lib/activities/search/use-activity-search';
import {
  parseSearchFiltersFromQuery,
  parseSearchViewMode,
} from '@/lib/activities/search-params';
import { sanitizeSearchFilters } from '@/lib/home-wizard/area-scope';
import { listingsWithCoordinates } from '@/lib/google-maps/coordinates';
import { isGoogleMapsEnabled } from '@/lib/google-maps/config';
import { trackSearch } from '@/lib/analytics/data-layer';

interface SearchResultsPageProps {
  readonly locale: Locale;
  readonly copy: SiteContent['searchPage'];
}

export function SearchResultsPage({ locale, copy }: SearchResultsPageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setFilters } = useSearchContext();
  const applyFilters = useApplySearchFilters(locale);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showAreaNotice, setShowAreaNotice] = useState(false);

  const searchKey = searchParams.toString();
  const urlFilterState = useMemo(
    () => sanitizeSearchFilters(parseSearchFiltersFromQuery(new URLSearchParams(searchKey))),
    [searchKey],
  );
  const urlFilters = urlFilterState.filters;
  const areaAdjusted = urlFilterState.adjusted;
  const urlViewMode = useMemo(
    () => parseSearchViewMode(searchParams),
    [searchParams],
  );
  const mapsEnabled = isGoogleMapsEnabled();
  const showMapSplit = mapsEnabled && urlViewMode === 'map';

  useEffect(() => {
    setFilters(urlFilters);
  }, [setFilters, urlFilters]);

  const replacementHref = buildSearchPageHref(locale, urlFilters, {
    view: urlViewMode,
  });
  useEffect(() => {
    rememberSearchHref(replacementHref);
  }, [replacementHref]);

  const announcedHref = useRef<string | null>(null);
  useEffect(() => {
    if (areaAdjusted) {
      setShowAreaNotice(true);
      announcedHref.current = replacementHref;
      router.replace(replacementHref);
      return;
    }
    if (
      announcedHref.current !== null &&
      replacementHref !== announcedHref.current
    ) {
      setShowAreaNotice(false);
      announcedHref.current = null;
    }
  }, [areaAdjusted, replacementHref, router]);

  const search = useActivitySearch({
    filters: urlFilters,
    locale,
    pageSize: SEARCH_RESULTS_PAGE_LIMIT,
    view: 'card',
    includeTotal: true,
  });
  const listings = search.items;
  const isLoading = search.isLoading;
  const categoryMatch = search.categoryMatch;
  const errorMessage = search.errorMessage ? copy.errorLabel : null;
  const loadMoreError = search.loadMoreError ? copy.errorLabel : null;

  useEffect(() => {
    if (!isLoading && !search.errorMessage) {
      trackSearch(urlFilters);
    }
  }, [isLoading, search.errorMessage, urlFilters]);

  useEffect(() => {
    if (!showMapSplit || listings.length === 0) {
      return;
    }
    if (
      selectedId &&
      listings.some((listing) => listing.activity.id === selectedId)
    ) {
      return;
    }
    const firstMappable = listingsWithCoordinates(listings)[0];
    setSelectedId(
      firstMappable?.activity.id ?? listings[0]?.activity.id ?? null,
    );
  }, [listings, selectedId, showMapSplit]);

  function navigateToListView() {
    router.push(buildSearchPageHref(locale, urlFilters, { view: 'list' }));
  }

  function navigateToMapView() {
    router.push(buildMapSearchHref(locale, urlFilters));
  }

  const viewToggle = mapsEnabled ? (
    <SearchViewToggle
      isMapView={showMapSplit}
      groupLabel={copy.viewToggleLabel}
      listLabel={copy.listViewLabel}
      mapLabel={copy.mapViewLabel}
      onShowList={navigateToListView}
      onShowMap={navigateToMapView}
    />
  ) : null;
  const showsMap = showMapSplit && !errorMessage;
  const noticeClassName =
    'mx-auto w-full max-w-7xl px-4 pt-3 text-sm text-ink-700 sm:px-6 md:pt-4 lg:px-8';

  return (
    <div className={showsMap ? 'search-page search-page--map bg-white' : 'search-page bg-white'}>
      <h1 className="sr-only">{copy.pageTitle}</h1>
      <FilterChipRow
        locale={locale}
        copy={copy}
        viewToggle={viewToggle}
        isMapView={showMapSplit}
      />
      <SearchResultsSummary
        locale={locale}
        copy={copy}
        filters={urlFilters}
        total={search.total}
        isLoading={isLoading}
        onApply={applyFilters}
        viewToggle={viewToggle}
      />
      {showAreaNotice ? (
        <p role="status" className={`${noticeClassName} max-md:pb-2`}>
          {copy.areaAdjustedLabel}
        </p>
      ) : null}
      {categoryMatch === 'legacy_fallback' ? (
        <p className={`${noticeClassName} max-md:pb-2`}>{copy.unsortedCategoryLabel}</p>
      ) : null}
      {errorMessage ? (
        <p className="mx-auto max-w-7xl px-4 py-6 text-center text-red-700">
          {errorMessage}
        </p>
      ) : null}
      <div className="search-page__results relative">
        {errorMessage ? null : showMapSplit ? (
          <div className="search-page__map-frame lg:mx-auto lg:max-w-7xl lg:px-8 lg:pt-4">
            <SearchMapSplitLayout
              locale={locale}
              copy={copy}
              listings={listings}
              selectedId={selectedId}
              onSelect={setSelectedId}
              isLoading={isLoading}
              loadMore={{
                hasMore: search.hasMore,
                isLoadingMore: search.isLoadingMore,
                errorMessage: loadMoreError,
                onLoadMore: search.loadMore,
              }}
            />
          </div>
        ) : (
          <div className="mx-auto max-w-7xl px-4 pb-10 pt-3 sm:px-6 md:pb-16 md:pt-4 lg:px-8">
            <ListingGrid
              locale={locale}
              listings={listings}
              isLoading={isLoading}
              labels={{
                parentVerified: copy.parentVerifiedLabel,
                freeTrial: copy.freeTrialLabel,
                imageFallback: copy.imageFallbackLabel,
                locationsCount: copy.locationsCountLabel,
                detailsOnRequest: copy.detailsOnRequestLabel,
                empty: copy.emptyLabel,
              }}
            />
          </div>
        )}
        {search.hasMore && !showMapSplit ? (
          <div className="mx-auto flex max-w-7xl flex-col items-center gap-3 px-4 py-8">
            {loadMoreError ? (
              <p className="text-center text-red-700">{loadMoreError}</p>
            ) : null}
            <button
              type="button"
              onClick={search.loadMore}
              disabled={search.isLoadingMore}
              className="min-h-11 rounded-full bg-brand-500 px-6 py-3 text-sm font-semibold text-ink-900 hover:bg-brand-600 disabled:opacity-60"
            >
              {copy.loadMoreLabel}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
