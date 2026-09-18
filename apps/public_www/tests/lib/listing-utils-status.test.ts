import { describe, expect, it } from 'vitest';

import {
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
  });

  it('detects template descriptions', () => {
    expect(isTemplateDescription(buildListing())).toBe(false);
    expect(
      isTemplateDescription(buildListing({ descriptionSource: 'template' })),
    ).toBe(true);
  });

  it('builds a Google Maps place URL only when placeId is set', () => {
    expect(googleMapsPlaceUrl(null)).toBeNull();
    expect(googleMapsPlaceUrl('ChIJ123')).toBe(
      'https://www.google.com/maps/search/?api=1&query_place_id=ChIJ123',
    );
  });
});
