'use client';

import { useEffect, useMemo, useState } from 'react';

import type { Locale, SiteContent } from '@/content';
import { useSearchContext } from '@/components/shared/search/search-context';
import { ListingCarouselSection } from '@/components/sections/listings/listing-carousel-section';
import { logActivityLoadError } from '@/lib/activities/load-error';
import { DISCOVERY_HOME_SEARCH_LIMIT } from '@/lib/activities/search-limits';
import { fetchActivitySearch } from '@/lib/activities/search-client';
import {
  buildSearchHref,
  regionIdForAreaId,
} from '@/lib/activities/map-search-url';
import {
  filtersToApiParams,
  type SearchFiltersState,
} from '@/lib/activities/search-params';
import {
  groupListingsByRegion,
  matchesTextQuery,
  sortListingsForDiscovery,
} from '@/lib/activities/listing-utils';
import { loadRecentSearch, loadRecentViewedIds } from '@/lib/activities/recent-storage';
import type { ActivityListing } from '@/lib/activities/types';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';

interface DiscoveryHomeSectionProps {
  readonly locale: Locale;
  readonly copy: SiteContent['discovery'];
}

async function fetchDiscoveryListings(
  locale: Locale,
  filters: SearchFiltersState,
): Promise<readonly ActivityListing[]> {
  const apiParams = filtersToApiParams(filters);
  const response = await fetchActivitySearch({
    ...apiParams,
    limit: DISCOVERY_HOME_SEARCH_LIMIT,
  });
  return sortListingsForDiscovery(
    response.items.filter((listing) =>
      matchesTextQuery(listing, locale, filters.textQuery),
    ),
  );
}

export function DiscoveryHomeSection({ locale, copy }: DiscoveryHomeSectionProps) {
  const { filters } = useSearchContext();
  const [listings, setListings] = useState<readonly ActivityListing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setErrorMessage(null);

    fetchDiscoveryListings(locale, filters)
      .then((items) => {
        if (!cancelled) {
          setListings(items);
        }
      })
      .catch((error: unknown) => {
        logActivityLoadError('discovery home', error);
        if (!cancelled) {
          setErrorMessage(copy.errorLabel);
          setListings([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [copy.errorLabel, filters, locale]);

  const recentSearchFilters = useMemo(() => loadRecentSearch(), []);
  const [recentListings, setRecentListings] = useState<readonly ActivityListing[]>(
    [],
  );

  useEffect(() => {
    if (!recentSearchFilters) {
      return;
    }
    fetchDiscoveryListings(locale, recentSearchFilters)
      .then((items) => setRecentListings(items.slice(0, 12)))
      .catch(() => setRecentListings([]));
  }, [locale, recentSearchFilters]);

  const viewedIds = useMemo(() => loadRecentViewedIds(), []);
  const viewedListings = useMemo(
    () =>
      listings.filter((listing) => viewedIds.includes(listing.activity.id)).slice(0, 12),
    [listings, viewedIds],
  );

  const popularListings = useMemo(
    () => listings.slice(0, 12),
    [listings],
  );

  const regionGroups = useMemo(
    () => groupListingsByRegion(listings),
    [listings],
  );

  const cardLabels = {
    parentVerified: copy.parentVerifiedLabel,
    freeTrial: copy.freeTrialLabel,
    imageFallback: copy.imageFallbackLabel,
    mapAlt: copy.mapAltLabel,
  };

  const carouselSections = useMemo(() => {
    const sections: Array<{
      readonly key: string;
      readonly title: string;
      readonly listings: readonly ActivityListing[];
      readonly isLoading: boolean;
      readonly searchHref: string;
    }> = [];

    if (recentSearchFilters && recentListings.length > 0) {
      sections.push({
        key: 'recent-search',
        title: copy.continueSearchingTitle,
        listings: recentListings,
        isLoading: false,
        searchHref: buildSearchHref(locale, recentSearchFilters),
      });
    }

    if (viewedListings.length > 0) {
      sections.push({
        key: 'recently-viewed',
        title: copy.recentlyViewedTitle,
        listings: viewedListings,
        isLoading: false,
        searchHref: buildSearchHref(locale, filters),
      });
    }

    sections.push({
      key: 'popular',
      title: copy.popularTitle,
      listings: popularListings,
      isLoading,
      searchHref: buildSearchHref(locale, filters),
    });

    for (const [regionKey, regionListings] of regionGroups.entries()) {
      const region = homeWizardChoices.regions.find(
        (entry) => entry.areaId === regionKey,
      );
      const title = region
        ? `${copy.nearRegionTitle} ${labelForLocale(region.labels, locale)}`
        : copy.nearRegionTitle;
      const regionId = regionIdForAreaId(regionKey);
      sections.push({
        key: `region-${regionKey}`,
        title,
        listings: regionListings.slice(0, 12),
        isLoading,
        searchHref: buildSearchHref(locale, {
          ...filters,
          regionId: regionId ?? filters.regionId,
        }),
      });
    }

    return sections;
  }, [
    copy.continueSearchingTitle,
    copy.nearRegionTitle,
    copy.popularTitle,
    copy.recentlyViewedTitle,
    filters,
    isLoading,
    locale,
    popularListings,
    recentListings,
    recentSearchFilters,
    regionGroups,
    viewedListings,
  ]);

  if (errorMessage) {
    return (
      <p className="mx-auto max-w-3xl px-4 py-12 text-center text-red-700">
        {errorMessage}
      </p>
    );
  }

  return (
    <div className="bg-white">
      {carouselSections.map((section, sectionIndex) => (
        <ListingCarouselSection
          key={section.key}
          locale={locale}
          title={section.title}
          searchHref={section.searchHref}
          seeAllLabel={copy.carousel.seeAllLabel}
          listings={section.listings}
          isLoading={section.isLoading}
          sectionIndex={sectionIndex}
          isPrimaryCarousel={sectionIndex === 0}
          labels={cardLabels}
        />
      ))}
    </div>
  );
}
