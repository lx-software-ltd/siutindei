'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { FilterChipRow } from '@/components/sections/search/filter-chip-row';
import { SearchMapSplitLayout } from '@/components/sections/search/search-map-split-layout';
import { SearchViewToggle } from '@/components/sections/search/search-view-toggle';
import { ListingGrid } from '@/components/sections/listings/listing-grid';
import { useSearchContext } from '@/components/shared/search/search-context';
import { SEARCH_RESULTS_PAGE_LIMIT } from '@/lib/activities/search-limits';
import { buildMapSearchHref, buildSearchPageHref } from '@/lib/activities/map-search-url';
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
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showAreaNotice, setShowAreaNotice] = useState(false);

  const ageParam = searchParams.get('age');
  const regionParam = searchParams.get('region');
  const neighbourhoodParam = searchParams.get('neighbourhood');
  const typesParam = searchParams.get('types');
  const queryParam = searchParams.get('q');
  const urlFilterState = useMemo(() => {
    const params = new URLSearchParams();
    if (ageParam) {
      params.set('age', ageParam);
    }
    if (regionParam) {
      params.set('region', regionParam);
    }
    if (neighbourhoodParam) {
      params.set('neighbourhood', neighbourhoodParam);
    }
    if (typesParam) {
      params.set('types', typesParam);
    }
    if (queryParam) {
      params.set('q', queryParam);
    }
    return sanitizeSearchFilters(parseSearchFiltersFromQuery(params));
  }, [ageParam, neighbourhoodParam, queryParam, regionParam, typesParam]);
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

  return (
    <div className="bg-white">
      <h1 className="sr-only">{copy.pageTitle}</h1>
      <FilterChipRow locale={locale} />
      {showAreaNotice ? (
        <p
          role="status"
          className="mx-auto max-w-7xl px-4 pt-4 text-sm text-ink-700 sm:px-6 lg:px-8"
        >
          {copy.areaAdjustedLabel}
        </p>
      ) : null}
      {categoryMatch === 'legacy_fallback' ? (
        <p className="mx-auto max-w-7xl px-4 pt-4 text-sm text-ink-700 sm:px-6 lg:px-8">
          {copy.unsortedCategoryLabel}
        </p>
      ) : null}
      {errorMessage ? (
        <p className="mx-auto max-w-7xl px-4 py-6 text-center text-red-700">
          {errorMessage}
        </p>
      ) : null}
      <div className="relative">
        {errorMessage ? null : showMapSplit ? (
          <SearchMapSplitLayout
            locale={locale}
            copy={copy}
            listings={listings}
            selectedId={selectedId}
            onSelect={setSelectedId}
            isLoading={isLoading}
          />
        ) : (
          <div className="mx-auto max-w-7xl px-4 pb-24 pt-8 sm:px-6 lg:px-8">
            <ListingGrid
              locale={locale}
              listings={listings}
              isLoading={isLoading}
              labels={{
                parentVerified: copy.parentVerifiedLabel,
                freeTrial: copy.freeTrialLabel,
                imageFallback: copy.imageFallbackLabel,
                mapAlt: copy.mapAltLabel,
                locationsCount: copy.locationsCountLabel,
                detailsOnRequest: copy.detailsOnRequestLabel,
                empty: copy.emptyLabel,
              }}
            />
          </div>
        )}
        {search.hasMore ? (
          <div className="mx-auto flex max-w-7xl flex-col items-center gap-3 px-4 py-8">
            {loadMoreError ? (
              <p className="text-center text-red-700">{loadMoreError}</p>
            ) : null}
            <button
              type="button"
              onClick={search.loadMore}
              disabled={search.isLoadingMore}
              className="rounded-full bg-brand-500 px-6 py-3 text-sm font-semibold text-ink-900 hover:bg-brand-600 disabled:opacity-60"
            >
              {copy.loadMoreLabel}
            </button>
          </div>
        ) : null}
        {mapsEnabled ? (
          <SearchViewToggle
            isMapView={showMapSplit}
            listLabel={copy.listViewLabel}
            mapLabel={copy.mapViewLabel}
            onShowList={navigateToListView}
            onShowMap={navigateToMapView}
          />
        ) : null}
      </div>
    </div>
  );
}
