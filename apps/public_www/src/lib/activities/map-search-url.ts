import type { Locale } from '@/content/locales';
import { homeWizardChoices } from '@/lib/home-wizard/choices';
import { localizePath } from '@/lib/locale-routing';
import type { ActivityListing } from '@/lib/activities/types';

import {
  buildSearchQueryString,
  type SearchFiltersState,
  type SearchViewMode,
} from './search-params';

export function regionIdForAreaId(areaId: string): string | null {
  const match = homeWizardChoices.regions.find(
    (region) => region.areaId === areaId,
  );
  return match?.id ?? null;
}

export function regionIdForListing(listing: ActivityListing): string | null {
  const areaId =
    listing.location.regionAreaId ?? listing.location.areaId;
  return regionIdForAreaId(areaId);
}

export function buildSearchPageHref(
  locale: Locale,
  filters: SearchFiltersState,
  extras?: { readonly view?: SearchViewMode },
): string {
  const query = buildSearchQueryString(filters, {
    view: extras?.view ?? 'map',
  });
  return `${localizePath('/search', locale)}?${query}`;
}

export function buildSearchHref(
  locale: Locale,
  filters: SearchFiltersState,
): string {
  return buildSearchPageHref(locale, filters, { view: 'map' });
}

export function buildMapSearchHref(
  locale: Locale,
  filters: SearchFiltersState,
): string {
  return buildSearchPageHref(locale, filters, { view: 'map' });
}

export function buildMapSearchHrefForRegion(
  locale: Locale,
  baseFilters: SearchFiltersState,
  regionId: string,
): string {
  return buildMapSearchHref(locale, {
    ...baseFilters,
    regionId,
  });
}

export type { SearchViewMode };
