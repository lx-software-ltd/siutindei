'use client';

import type { ListingCarouselLabels } from '@/components/sections/listings/listing-carousel-section';
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { formatContentTemplate } from '@/content/content-field-utils';
import { useSearchContext } from '@/components/shared/search/search-context';
import { ListingCarouselSection } from '@/components/sections/listings/listing-carousel-section';
import {
  buildSearchHref,
  regionIdForAreaId,
  regionIdForListing,
} from '@/lib/activities/map-search-url';
import {
  DISCOVERY_HOME_SEARCH_LIMIT,
  DISCOVERY_RECENT_SEARCH_LIMIT,
} from '@/lib/activities/search-limits';
import { useActivitySearch } from '@/lib/activities/search/use-activity-search';
import {
  placeLabelForFilters,
  type SearchFiltersState,
} from '@/lib/activities/search-params';
import { sortListingsForDiscovery } from '@/lib/activities/listing-utils';
import {
  getRecentSearchServerSnapshot,
  getRecentSearchSnapshot,
  loadRecentViewedIds,
  subscribeRecentSearch,
} from '@/lib/activities/recent-storage';
import type { ActivityListing } from '@/lib/activities/types';
import {
  homeWizardChoices,
  labelForLocale,
  REGIONS_BY_ID,
} from '@/lib/home-wizard/choices';
import {
  joinPlaceNames,
  namedOpenPlace,
  namedOpenPlaceInRegion,
  type PlaceListCopy,
} from '@/lib/home-wizard/area-scope';

interface DiscoveryHomeSectionProps {
  readonly locale: Locale;
  readonly copy: SiteContent['discovery'];
  /** The page also links to pre-rendered activity pages, so a failed search can stay silent. */
  readonly hasStaticCatalogue?: boolean;
}

type CardLabels = ListingCarouselLabels;

function placeListCopy(copy: SiteContent['discovery']): PlaceListCopy {
  return {
    comma: copy.placeListComma,
    pairTemplate: copy.placePairTemplate,
    finalTemplate: copy.placeFinalTemplate,
  };
}

function DeferredCarousel({
  active,
  onVisible,
  children,
}: {
  readonly active: boolean;
  readonly onVisible?: () => void;
  readonly children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(active);

  useEffect(() => {
    if (visible) {
      onVisible?.();
    }
  }, [onVisible, visible]);

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

function ContinueSearchingSection({
  locale,
  copy,
  filters,
  cardLabels,
}: {
  readonly locale: Locale;
  readonly copy: SiteContent['discovery'];
  readonly filters: SearchFiltersState;
  readonly cardLabels: CardLabels;
}) {
  const [enabled, setEnabled] = useState(false);
  const show = useCallback(() => setEnabled(true), []);
  const recent = useActivitySearch({
    filters,
    locale,
    pageSize: DISCOVERY_RECENT_SEARCH_LIMIT,
    enabled,
    view: 'card',
  });
  if (enabled && !recent.isLoading && recent.items.length === 0) {
    return null;
  }
  return (
    <DeferredCarousel active={false} onVisible={show}>
      <ListingCarouselSection
        locale={locale}
        title={copy.continueSearchingTitle}
        searchHref={buildSearchHref(locale, filters)}
        seeAllLabel={copy.carousel.seeAllLabel}
        listings={recent.items.slice(0, 12)}
        isLoading={!enabled || recent.isLoading}
        sectionIndex={2}
        labels={cardLabels}
      />
    </DeferredCarousel>
  );
}

function RegionCarousel({
  locale,
  copy,
  filters,
  regionKey,
  seed,
  cardLabels,
  sectionIndex,
}: {
  readonly locale: Locale;
  readonly copy: SiteContent['discovery'];
  readonly filters: SearchFiltersState;
  readonly regionKey: string;
  readonly seed: readonly ActivityListing[];
  readonly cardLabels: CardLabels;
  readonly sectionIndex: number;
}) {
  const [enabled, setEnabled] = useState(false);
  const show = useCallback(() => setEnabled(true), []);
  const regionId = regionIdForAreaId(regionKey);
  const regionFilters = useMemo(
    () => ({
      ...filters,
      regionId: regionId ?? filters.regionId,
      neighbourhoodId: null,
    }),
    [filters, regionId],
  );
  const search = useActivitySearch({
    filters: regionFilters,
    locale,
    pageSize: 12,
    view: 'card',
    enabled: enabled && regionId !== null,
  });
  const region = homeWizardChoices.regions.find(
    (entry) => entry.areaId === regionKey,
  );
  const regionName = region ? labelForLocale(region.labels, locale) : '';
  const named = region
    ? namedOpenPlaceInRegion(region.id, locale)
    : { kind: 'unrestricted' as const };
  const place =
    named.kind === 'named'
      ? joinPlaceNames(named.names, placeListCopy(copy))
      : regionName;
  const title = place ? `${copy.nearRegionTitle} ${place}` : copy.nearRegionTitle;
  const listings = search.items.length > 0 ? search.items : seed;
  return (
    <DeferredCarousel active={false} onVisible={show}>
      <ListingCarouselSection
        locale={locale}
        title={title}
        searchHref={buildSearchHref(locale, regionFilters)}
        seeAllLabel={copy.carousel.seeAllLabel}
        listings={listings.slice(0, 12)}
        isLoading={search.isLoading && listings.length === 0}
        sectionIndex={sectionIndex}
        labels={cardLabels}
      />
    </DeferredCarousel>
  );
}

export function DiscoveryHomeSection({
  locale,
  copy,
  hasStaticCatalogue = false,
}: DiscoveryHomeSectionProps) {
  const { filters } = useSearchContext();
  const openPlace = namedOpenPlace(locale);
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
    enabled: openPlace.kind !== 'none',
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
  const regionGroups = useMemo(() => {
    const groups = new Map<string, ActivityListing[]>();
    for (const listing of listings) {
      const regionId = regionIdForListing(listing);
      const areaId = regionId ? REGIONS_BY_ID.get(regionId)?.areaId : null;
      if (!areaId) {
        continue;
      }
      const bucket = groups.get(areaId) ?? [];
      bucket.push(listing);
      groups.set(areaId, bucket);
    }
    return groups;
  }, [listings]);

  const cardLabels = {
    parentVerified: copy.parentVerifiedLabel,
    freeTrial: copy.freeTrialLabel,
    imageFallback: copy.imageFallbackLabel,
    locationsCount: copy.locationsCountLabel,
    detailsOnRequest: copy.detailsOnRequestLabel,
    previous: copy.previousLabel,
    next: copy.nextLabel,
  };

  if (primary.errorMessage) {
    if (hasStaticCatalogue) {
      return null;
    }
    return (
      <p className="mx-auto max-w-3xl px-4 py-12 text-center text-red-700">
        {copy.errorLabel}
      </p>
    );
  }

  const regionEntries = [...regionGroups.entries()];
  if (openPlace.kind === 'none') {
    return (
      <p
        role="status"
        className="mx-auto max-w-3xl px-4 py-12 text-center text-ink-700"
      >
        {copy.noAreasOpenLabel}
      </p>
    );
  }
  const selectedPlace = placeLabelForFilters(filters, locale);
  const popularTitle = selectedPlace
    ? formatContentTemplate(copy.popularInPlaceTemplate, { place: selectedPlace })
    : openPlace.kind === 'named'
      ? formatContentTemplate(copy.popularInPlaceTemplate, {
          place: joinPlaceNames(openPlace.names, placeListCopy(copy)),
        })
      : openPlace.kind === 'generic'
        ? copy.popularOpenAreasTitle
        : copy.popularTitle;

  return (
    <div className="bg-white">
      <DeferredCarousel active>
        <ListingCarouselSection
          locale={locale}
          title={popularTitle}
          searchHref={buildSearchHref(locale, filters)}
          seeAllLabel={copy.carousel.seeAllLabel}
          listings={popularListings}
          isLoading={primary.isLoading}
          sectionIndex={0}
          isPrimaryCarousel
          labels={cardLabels}
        />
      </DeferredCarousel>
      {viewedListings.length > 0 ? (
        <DeferredCarousel active={false}>
          <ListingCarouselSection
            locale={locale}
            title={copy.recentlyViewedTitle}
            searchHref={buildSearchHref(locale, filters)}
            seeAllLabel={copy.carousel.seeAllLabel}
            listings={viewedListings}
            isLoading={false}
            sectionIndex={1}
            labels={cardLabels}
          />
        </DeferredCarousel>
      ) : null}
      {recentSearchFilters ? (
        <ContinueSearchingSection
          locale={locale}
          copy={copy}
          filters={recentSearchFilters}
          cardLabels={cardLabels}
        />
      ) : null}
      {regionEntries.length > 1
        ? regionEntries.map(([regionKey, seed], index) => (
            <RegionCarousel
              key={regionKey}
              locale={locale}
              copy={copy}
              filters={filters}
              regionKey={regionKey}
              seed={seed}
              cardLabels={cardLabels}
              sectionIndex={index + 3}
            />
          ))
        : null}
    </div>
  );
}
