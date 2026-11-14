import { describe, expect, it } from 'vitest';

import type { ActivityListing } from '@/lib/activities/types';
import { filterWizardResults } from '@/lib/home-wizard/filter-results';

function buildListing(
  partial: Pick<ActivityListing, 'activity' | 'organization' | 'location'>,
): ActivityListing {
  return {
    ...partial,
    pricing: {
      pricingType: 'per_class',
      amount: 100,
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

const sampleItems: readonly ActivityListing[] = [
  buildListing({
    activity: {
      id: '1',
      name: 'Painting',
      description: 'Art class',
      nameTranslations: {},
      descriptionTranslations: {},
      ageMin: null,
      ageMax: null,
      categoryId: 'c1',
      kind: 'class',
      facts: {},
      categoryRootId: 'c1',
      categoryName: null,
      categoryNameTranslations: {},
    },
    organization: {
      id: 'o1',
      name: 'Studio',
      description: null,
      nameTranslations: {},
      mediaUrls: [],
      logoMediaUrl: null,
    },
    location: {
      id: 'l1',
      areaId: 'district-1',
      regionAreaId: 'region-hk-island',
      address: null,
      lat: null,
      lng: null,
    },
  }),
  buildListing({
    activity: {
      id: '2',
      name: 'Dance',
      description: 'Movement',
      nameTranslations: {},
      descriptionTranslations: {},
      ageMin: null,
      ageMax: null,
      categoryId: 'c2',
      kind: 'class',
      facts: {},
      categoryRootId: 'c2',
      categoryName: null,
      categoryNameTranslations: {},
    },
    organization: {
      id: 'o2',
      name: 'Dance Co',
      description: null,
      nameTranslations: {},
      mediaUrls: [],
      logoMediaUrl: null,
    },
    location: {
      id: 'l2',
      areaId: 'district-2',
      regionAreaId: 'region-kowloon',
      address: null,
      lat: null,
      lng: null,
    },
  }),
];

describe('filterWizardResults', () => {
  it('filters by macro region', () => {
    const filtered = filterWizardResults(
      sampleItems,
      'region-hk-island',
      '',
    );
    expect(filtered).toHaveLength(1);
    expect(filtered[0]?.activity.name).toBe('Painting');
  });

  it('applies free-text search on filtered region results', () => {
    const filtered = filterWizardResults(
      sampleItems,
      'region-kowloon',
      'dance',
    );
    expect(filtered).toHaveLength(1);
    expect(filtered[0]?.activity.name).toBe('Dance');
  });
});
