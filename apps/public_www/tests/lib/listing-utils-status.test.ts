import { describe, expect, it } from 'vitest';

import {
  formatListingPrice,
  googleMapsPlaceUrl,
  isTemplateDescription,
  isTemporarilyClosed,
} from '@/lib/activities/listing-utils';
import type { ActivityListing } from '@/lib/activities/types';

function buildListing(
  overrides: Partial<ActivityListing['organization']> = {},
): ActivityListing {
  return {
    activity: {
      id: 'act-1',
      name: 'Park',
      description: null,
      nameTranslations: {},
      descriptionTranslations: {},
      ageMin: 1,
      ageMax: 8,
      categoryId: null,
    },
    organization: {
      id: 'org-1',
      name: 'Park Org',
      description: null,
      nameTranslations: {},
      mediaUrls: [],
      logoMediaUrl: null,
      status: 'operational',
      descriptionSource: null,
      placeId: null,
      ...overrides,
    },
    location: {
      id: 'loc-1',
      areaId: 'area-1',
      regionAreaId: null,
      address: null,
      lat: null,
      lng: null,
    },
    pricing: {
      pricingType: 'free',
      amount: 0,
      currency: 'HKD',
      sessionsCount: null,
      freeTrialClassOffered: false,
    },
    schedule: {
      scheduleType: 'weekly',
      weeklyEntries: [],
      languages: [],
    },
  };
}

describe('listing status helpers', () => {
  it('detects temporarily closed listings', () => {
    expect(isTemporarilyClosed(buildListing())).toBe(false);
    expect(
      isTemporarilyClosed(buildListing({ status: 'closed_temporarily' })),
    ).toBe(true);
    const listing = buildListing();
    expect(
      isTemporarilyClosed({
        ...listing,
        location: { ...listing.location, status: 'temporarily_closed' },
      }),
    ).toBe(true);
  });

  it('detects template descriptions', () => {
    expect(isTemplateDescription(buildListing())).toBe(false);
    expect(
      isTemplateDescription(buildListing({ descriptionSource: 'template' })),
    ).toBe(true);
    expect(
      isTemplateDescription(
        buildListing({
          descriptionSource: 'template',
          description: 'Saturday art class for children in the harbour.',
        }),
      ),
    ).toBe(false);
    expect(
      isTemplateDescription(
        buildListing({
          descriptionSource: 'template',
          description:
            'Harbour Club is a class or early-years centre in CENTRAL for children and families.',
        }),
      ),
    ).toBe(true);
    expect(
      isTemplateDescription(
        buildListing({
          descriptionSource: 'template',
          description:
            'Harbour Park is a indoor family venue in Yau Tsim Mong for children and families.',
        }),
      ),
    ).toBe(true);
    expect(
      isTemplateDescription(
        buildListing({
          descriptionSource: 'template',
          description: 'Saturday art class for children and families in the harbour.',
        }),
      ),
    ).toBe(false);
  });

  it('builds a Google Maps place URL only when placeId is set', () => {
    expect(googleMapsPlaceUrl(null)).toBeNull();
    expect(googleMapsPlaceUrl('ChIJ123')).toBe(
      'https://www.google.com/maps/search/?api=1&query_place_id=ChIJ123',
    );
  });

  it('formats monthly tuition and a yearly levy', () => {
    const monthly = buildListing();
    const yearly = buildListing();
    const monthListing = {
      ...monthly,
      pricing: { ...monthly.pricing, pricingType: 'per_month', amount: 3800 },
    };
    const yearListing = {
      ...yearly,
      pricing: { ...yearly.pricing, pricingType: 'per_year', amount: 35000 },
    };
    expect(formatListingPrice('en', monthListing)).toBe('HK$3,800 / month');
    expect(formatListingPrice('zh-HK', monthListing)).toBe('HK$3,800 / 月');
    expect(formatListingPrice('en', yearListing)).toBe('HK$35,000 / year');
    expect(formatListingPrice('zh-HK', yearListing)).toBe('HK$35,000 / 年');
  });
});
