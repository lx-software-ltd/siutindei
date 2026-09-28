'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import type { Locale, SiteContent } from '@/content';
import { FilterChipRow } from '@/components/sections/search/filter-chip-row';
import { SearchMapSplitLayout } from '@/components/sections/search/search-map-split-layout';
import { SearchViewToggle } from '@/components/sections/search/search-view-toggle';
import { ListingGrid } from '@/components/sections/listings/listing-grid';
import { useSearchContext } from '@/components/shared/search/search-context';
import { SEARCH_RESULTS_PAGE_LIMIT } from '@/lib/activities/search-limits';
import { fetchActivitySearch } from '@/lib/activities/search-client';
import { buildMapSearchHref } from '@/lib/activities/map-search-url';
import {
  buildSearchQueryString,
  filtersToApiParams,
  parseSearchFiltersFromQuery,
  parseSearchViewMode,
} from '@/lib/activities/search-params';
import { matchesTextQuery } from '@/lib/activities/listing-utils';
import { listingsWithCoordinates } from '@/lib/google-maps/coordinates';
import { isGoogleMapsEnabled } from '@/lib/google-maps/config';
import { localizePath } from '@/lib/locale-routing';
import type { ActivityListing } from '@/lib/activities/types';
import { trackSearch } from '@/lib/analytics/data-layer';

interface SearchResultsPageProps {
  readonly locale: Locale;
  readonly copy: SiteContent['searchPage'];
}

export function SearchResultsPage({ locale, copy }: SearchResultsPageProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setFilters } = useSearchContext();
  const [listings, setListings] = useState<readonly ActivityListing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const ageParam = searchParams.get('age');
  const regionParam = searchParams.get('region');
  const typesParam = searchParams.get('types');
  const queryParam = searchParams.get('q');
  const urlFilters = useMemo(() => {
    const params = new URLSearchParams();
    if (ageParam) {
      params.set('age', ageParam);
    }
    if (regionParam) {
      params.set('region', regionParam);
    }
    if (typesParam) {
      params.set('types', typesParam);
    }
    if (queryParam) {
      params.set('q', queryParam);
    }
    return parseSearchFiltersFromQuery(params);
  }, [ageParam, queryParam, regionParam, typesParam]);
  const urlViewMode = useMemo(
    () => parseSearchViewMode(searchParams),
    [searchParams],
  );
  const mapsEnabled = isGoogleMapsEnabled();
  const showMapSplit = mapsEnabled && urlViewMode === 'map';

  useEffect(() => {
    setFilters(urlFilters);
  }, [setFilters, urlFilters]);

  const loadResults = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const apiParams = filtersToApiParams(urlFilters);
      const response = await fetchActivitySearch({
        ...apiParams,
        limit: SEARCH_RESULTS_PAGE_LIMIT,
      });
      const filtered = response.items.filter((listing) =>
        matchesTextQuery(listing, locale, urlFilters.textQuery),
      );
      setListings(filtered);
      trackSearch(urlFilters);
    } catch {
      setErrorMessage(copy.errorLabel);
      setListings([]);
    } finally {
      setIsLoading(false);
    }
  }, [copy.errorLabel, locale, urlFilters]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

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
    const query = buildSearchQueryString(urlFilters, { view: 'list' });
    const path = localizePath('/search', locale);
    router.push(`${path}?${query}`);
  }

  function navigateToMapView() {
    router.push(buildMapSearchHref(locale, urlFilters));
  }

  return (
    <div className="bg-white">
      <h1 className="sr-only">{copy.pageTitle}</h1>
      <FilterChipRow locale={locale} />
      {errorMessage ? (
        <p className="mx-auto max-w-7xl px-4 py-6 text-center text-red-700">
          {errorMessage}
        </p>
      ) : null}
      <div className="relative">
        {showMapSplit ? (
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
                empty: copy.emptyLabel,
              }}
            />
          </div>
        )}
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
