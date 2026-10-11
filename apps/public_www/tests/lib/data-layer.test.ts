import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { ANALYTICS_CONSENT_STORAGE_KEY } from '@/lib/analytics/consent';
import {
  itemFieldsFromListing,
  pushDataLayerEvent,
  searchFieldsFromFilters,
  trackGenerateLead,
  trackSearch,
  trackViewItem,
} from '@/lib/analytics/data-layer';
import type { ActivityListing } from '@/lib/activities/types';
import { DEFAULT_SEARCH_FILTERS } from '@/lib/activities/search-params';

function buildListing(): ActivityListing {
  return {
    activity: {
      id: 'act-1',
      name: 'Kowloon art',
      description: null,
      nameTranslations: { 'zh-HK': '九龍藝術' },
      descriptionTranslations: {},
      ageMin: null,
      ageMax: null,
      categoryId: 'c1111111-1111-1111-1111-111111111101',
    },
    organization: {
      id: 'org-1',
      name: 'Studio',
      description: null,
      nameTranslations: {},
      mediaUrls: [],
      logoMediaUrl: null,
    },
    location: {
      id: 'loc-1',
      areaId: 'a1111111-1111-1111-1111-111111111102',
      regionAreaId: 'a1111111-1111-1111-1111-111111111102',
      address: null,
      lat: 22.3193,
      lng: 114.1694,
    },
    pricing: {
      pricingType: 'per_class',
      amount: 180,
      currency: 'hkd',
      sessionsCount: null,
      freeTrialClassOffered: false,
    },
    schedule: {
      scheduleType: 'weekly',
      weeklyEntries: [],
      languages: ['en'],
    },
  };
}

describe('dataLayer helpers', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.dataLayer = [];
  });

  afterEach(() => {
    window.localStorage.clear();
    delete window.dataLayer;
  });

  it('does not push when analytics consent is missing', () => {
    pushDataLayerEvent({
      event: 'generate_lead',
      lead_type: 'whatsapp_fab',
    });

    expect(window.dataLayer).toEqual([]);
  });

  it('does not push when analytics consent is denied', () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'denied');

    trackGenerateLead('whatsapp_footer');

    expect(window.dataLayer).toEqual([]);
  });

  it('pushes generate_lead after consent is granted', () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');

    trackGenerateLead('whatsapp_fab');

    expect(window.dataLayer).toEqual([
      { event: 'generate_lead', lead_type: 'whatsapp_fab' },
    ]);
  });

  it('maps listing fields for view_item including uppercase currency', () => {
    const listing = buildListing();
    expect(itemFieldsFromListing('en', listing)).toEqual({
      item_id: 'act-1',
      item_name: 'Kowloon art',
      item_brand: 'Studio',
      price: 180,
      currency: 'HKD',
    });
    expect(itemFieldsFromListing('zh-HK', listing).item_name).toBe(
      '九龍藝術',
    );

    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');
    trackViewItem('en', listing);

    expect(window.dataLayer).toEqual([
      {
        event: 'view_item',
        item_id: 'act-1',
        item_name: 'Kowloon art',
        item_brand: 'Studio',
        price: 180,
        currency: 'HKD',
      },
    ]);
  });

  it('includes item fields on the activity WhatsApp lead', () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');
    const item = itemFieldsFromListing('en', buildListing());

    trackGenerateLead('whatsapp_activity', item);

    expect(window.dataLayer).toEqual([
      {
        event: 'generate_lead',
        lead_type: 'whatsapp_activity',
        ...item,
      },
    ]);
  });

  it('maps available search filters and omits empty ones', () => {
    expect(searchFieldsFromFilters(DEFAULT_SEARCH_FILTERS)).toEqual({
      age: 4,
    });
    expect(
      searchFieldsFromFilters({
        ageGroupId: '3-6',
        regionId: 'kowloon',
        neighbourhoodId: null,
        activityTypeIds: ['early-years', 'learning'],
        textQuery: '  pottery  ',
      }),
    ).toEqual({
      search_term: 'pottery',
      area_id: 'a1111111-1111-1111-1111-111111111102',
      age: 4,
      category_id:
        'c1111111-1111-1111-1111-111111111201,c1111111-1111-1111-1111-111111111202',
    });
  });

  it('pushes search after consent is granted', () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');

    trackSearch({
      ageGroupId: '6-12',
      regionId: null,
      neighbourhoodId: null,
      activityTypeIds: [],
      textQuery: '',
    });

    expect(window.dataLayer).toEqual([{ event: 'search', age: 9 }]);
  });
});
