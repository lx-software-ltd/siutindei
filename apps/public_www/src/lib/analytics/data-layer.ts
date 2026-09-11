import { hasAnalyticsConsent } from '@/lib/analytics/consent';
import {
  ingestListingEvents,
  type ListingEventPayload,
} from '@/lib/analytics/listing-events-ingest';
import {
  listingOrgName,
  listingTitle,
} from '@/lib/activities/listing-utils';
import {
  filtersToApiParams,
  type SearchFiltersState,
} from '@/lib/activities/search-params';
import type { ActivityListing } from '@/lib/activities/types';
import type { Locale } from '@/content';

export type LeadType =
  | 'whatsapp_activity'
  | 'whatsapp_fab'
  | 'whatsapp_footer';

export interface AnalyticsItemFields {
  readonly item_id: string;
  readonly item_name: string;
  readonly item_brand: string;
  readonly price: number;
  readonly currency: string;
}

export interface AnalyticsSearchFields {
  readonly search_term?: string;
  readonly area_id?: string;
  readonly age?: number;
  readonly category_id?: string;
}

export interface GenerateLeadFields extends Partial<AnalyticsItemFields> {
  readonly lead_type: LeadType;
}

export type DataLayerEvent =
  | ({ readonly event: 'view_item' } & AnalyticsItemFields)
  | ({ readonly event: 'generate_lead' } & GenerateLeadFields)
  | ({ readonly event: 'search' } & AnalyticsSearchFields);

declare global {
  interface Window {
    dataLayer?: Array<Record<string, unknown>>;
  }
}

function omitEmpty(
  params: Record<string, unknown>,
): Record<string, unknown> {
  const compact: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      compact[key] = value;
    }
  }
  return compact;
}

export function pushDataLayerEvent(payload: DataLayerEvent): void {
  if (typeof window === 'undefined' || !hasAnalyticsConsent()) {
    return;
  }

  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(omitEmpty({ ...payload }));
}

export function itemFieldsFromListing(
  locale: Locale,
  listing: ActivityListing,
): AnalyticsItemFields {
  return {
    item_id: listing.activity.id,
    item_name: listingTitle(locale, listing),
    item_brand: listingOrgName(locale, listing),
    price: listing.pricing.amount,
    currency: listing.pricing.currency.toUpperCase(),
  };
}

export function searchFieldsFromFilters(
  filters: SearchFiltersState,
): AnalyticsSearchFields {
  const apiParams = filtersToApiParams(filters);
  const searchTerm = filters.textQuery.trim();
  return {
    ...(searchTerm ? { search_term: searchTerm } : {}),
    ...(apiParams.areaId ? { area_id: apiParams.areaId } : {}),
    ...(apiParams.age !== undefined ? { age: apiParams.age } : {}),
    ...(apiParams.categoryIds.length > 0
      ? { category_id: apiParams.categoryIds.join(',') }
      : {}),
  };
}

export interface ListingIds {
  readonly locationId?: string;
  readonly activityId?: string;
}

export function trackViewItem(
  locale: Locale,
  listing: ActivityListing,
): void {
  pushDataLayerEvent({
    event: 'view_item',
    ...itemFieldsFromListing(locale, listing),
  });
  if (!hasAnalyticsConsent()) {
    return;
  }
  void ingestListingEvents([
    {
      event_type: 'listing_view',
      location_id: listing.location.id,
      activity_id: listing.activity.id,
    },
  ]);
}

export function trackGenerateLead(
  leadType: LeadType,
  item?: AnalyticsItemFields,
  listingIds?: ListingIds,
): void {
  pushDataLayerEvent({
    event: 'generate_lead',
    lead_type: leadType,
    ...item,
  });
  if (!hasAnalyticsConsent()) {
    return;
  }
  const shared = {
    ...(listingIds?.locationId
      ? { location_id: listingIds.locationId }
      : {}),
    ...(listingIds?.activityId
      ? { activity_id: listingIds.activityId }
      : {}),
  };
  const events: ListingEventPayload[] = [
    { event_type: 'cta_tap', ...shared },
  ];
  if (leadType === 'whatsapp_activity') {
    events.push({ event_type: 'lead_relayed', ...shared });
  }
  void ingestListingEvents(events);
}

export function trackSearch(filters: SearchFiltersState): void {
  pushDataLayerEvent({
    event: 'search',
    ...searchFieldsFromFilters(filters),
  });
  if (!hasAnalyticsConsent()) {
    return;
  }
  void ingestListingEvents([{ event_type: 'search' }]);
}
