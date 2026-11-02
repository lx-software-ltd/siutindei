'use client';

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { useSearchContext } from '@/components/shared/search/search-context';
import { ListingCarouselSection } from '@/components/sections/listings/listing-carousel-section';
import { buildSearchHref, regionIdForAreaId } from '@/lib/activities/map-search-url';
import {
  DISCOVERY_HOME_SEARCH_LIMIT,
  DISCOVERY_RECENT_SEARCH_LIMIT,
} from '@/lib/activities/search-limits';
import { useActivitySearch } from '@/lib/activities/search/use-activity-search';
import {
  groupListingsByRegion,
  sortListingsForDiscovery,
} from '@/lib/activities/listing-utils';
import {
  getRecentSearchServerSnapshot,
  getRecentSearchSnapshot,
  loadRecentViewedIds,
  subscribeRecentSearch,
} from '@/lib/activities/recent-storage';
import type { ActivityListing } from '@/lib/activities/types';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';

interface DiscoveryHomeSectionProps {
  readonly locale: Locale;
  readonly copy: SiteContent['discovery'];
}

function DeferredCarousel({
  active,
  children,
}: {
  readonly active: boolean;
  readonly children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(active);

  useEffect(() => {
    if (active || visible) {
      return;
    }
    const node = ref.current;
    const Observer = globalThis.IntersectionObserver;
    if (!node || typeof Observer !== 'function') {
      setVisible(true);
      return;
    }
    const observer = new Observer(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '240px' },
    );
    observer.observe(node);
    return () => {
      observer.disconnect();
    };
  }, [active, visible]);

  return <div ref={ref}>{visible ? children : <div className="min-h-40" />}</div>;
}

export function DiscoveryHomeSection({ locale, copy }: DiscoveryHomeSectionProps) {
  const { filters } = useSearchContext();
  const recentSearchFilters = useSyncExternalStore(
    subscribeRecentSearch,
    getRecentSearchSnapshot,
    getRecentSearchServerSnapshot,
  );
  const primary = useActivitySearch({
    filters,
    locale,
    pageSize: DISCOVERY_HOME_SEARCH_LIMIT,
    view: 'card',
  });
  const recent = useActivitySearch({
    filters: recentSearchFilters ?? filters,
    locale,
    pageSize: DISCOVERY_RECENT_SEARCH_LIMIT,
    enabled: recentSearchFilters !== null && !primary.isLoading,
    view: 'card',
  });

  const listings = useMemo(
    () => sortListingsForDiscovery(primary.items),
    [primary.items],
  );
  const [viewedIds, setViewedIds] = useState<readonly string[]>([]);
  useEffect(() => {
    setViewedIds(loadRecentViewedIds());
  }, []);
  const viewedListings = useMemo(
    () =>
      listings.filter((listing) => viewedIds.includes(listing.activity.id)).slice(0, 12),
    [listings, viewedIds],
  );
  const popularListings = useMemo(() => listings.slice(0, 12), [listings]);
  const regionGroups = useMemo(() => groupListingsByRegion(listings), [listings]);

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

    if (recentSearchFilters && recent.items.length > 0) {
      sections.push({
        key: 'recent-search',
        title: copy.continueSearchingTitle,
        listings: recent.items.slice(0, 12),
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
      isLoading: primary.isLoading,
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
        isLoading: primary.isLoading,
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
    locale,
    popularListings,
    primary.isLoading,
    recent.items,
    recentSearchFilters,
    regionGroups,
    viewedListings,
  ]);

  if (primary.errorMessage) {
    return (
      <p className="mx-auto max-w-3xl px-4 py-12 text-center text-red-700">
        {copy.errorLabel}
      </p>
    );
  }

  return (
    <div className="bg-white">
      {carouselSections.map((section, sectionIndex) => (
        <DeferredCarousel key={section.key} active={sectionIndex === 0}>
          <ListingCarouselSection
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
        </DeferredCarousel>
      ))}
    </div>
  );
}
