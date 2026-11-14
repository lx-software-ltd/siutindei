import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { getContent } from '@/content';
import { activityBreadcrumbItems, activityStructuredData } from '@/lib/activities/activity-page-data';
import { landingCoverage, landingFacts } from '@/lib/activities/landing-page-data';
import {
  categoryLabelForListing,
  checkedFacts,
  formatMonthYear,
  listingAgeLabel,
  topicForListing,
} from '@/lib/activities/listing-facts';
import { mapActivityListing } from '@/lib/activities/map-listing';
import { classPriceEquivalent, formatListingPriceSummary } from '@/lib/activities/price-format';
import { homeWizardChoices } from '@/lib/home-wizard/choices';

import { buildListing, buildPricing } from '../helpers/listing-fixture';

const pageCopy = getContent('en').activitiesPage;
const [artsTopic] = homeWizardChoices.activityTypes;
const LEAF_CATEGORY_ID = 'c1111111-1111-1111-1111-111111119999';

const wireRow = (
  JSON.parse(
    readFileSync(join(process.cwd(), 'tests/fixtures/catalogue-snapshot.json'), 'utf8'),
  ) as { items: Array<Record<string, Record<string, unknown>>> }
).items[0];

describe('mapping the wire listing', () => {
  it('reads a missing kind as a class and keeps only checked facts', () => {
    const listing = mapActivityListing(
      { ...wireRow, activity: { ...wireRow.activity, facts: { toilets: true, shade: 'yes' } } } as never,
      'full',
    );

    expect(listing.activity.kind).toBe('class');
    expect(listing.activity.facts).toEqual({ toilets: true });
    expect(listing.activity.categoryRootId).toBe(listing.activity.categoryId);
  });

  it('dates the parent check only for a verified organiser', () => {
    const row = {
      ...wireRow,
      activity: { ...wireRow.activity, kind: 'place' },
      organization: {
        ...wireRow.organization,
        parent_verified: false,
        parent_verified_at: '2026-10-01T00:00:00Z',
      },
    };

    const unverified = mapActivityListing(row as never, 'full');
    expect(unverified.activity.kind).toBe('place');
    expect(unverified.organization.parentVerifiedAt).toBeNull();

    const verified = mapActivityListing(
      { ...row, organization: { ...row.organization, parent_verified: true } } as never,
      'full',
    );
    expect(verified.organization.parentVerifiedAt).toBe('2026-10-01T00:00:00Z');
  });
});

describe('listing facts by kind', () => {
  it('finds the topic through the root category', () => {
    const listing = buildListing({
      activity: { categoryId: LEAF_CATEGORY_ID, categoryRootId: artsTopic.categoryId },
    });

    expect(topicForListing(listing)?.id).toBe(artsTopic.id);
    expect(categoryLabelForListing('en', listing)).toBe(artsTopic.labels.en);
  });

  it('labels a place by its own category name', () => {
    const place = buildListing({
      activity: {
        kind: 'place',
        categoryName: 'Playground',
        categoryNameTranslations: { 'zh-HK': '遊樂場' },
      },
    });

    expect(categoryLabelForListing('en', place)).toBe('Playground');
    expect(categoryLabelForListing('zh-HK', place)).toBe('遊樂場');
  });

  it('leaves out ages for places and for catch-all ranges', () => {
    expect(listingAgeLabel('en', buildListing({ activity: { kind: 'place' } }))).toBeNull();
    expect(listingAgeLabel('en', buildListing({ activity: { ageMin: 0, ageMax: 18 } }))).toBeNull();
    expect(listingAgeLabel('en', buildListing({ activity: { kind: 'camp', ageMin: 5, ageMax: 9 } }))).toBe(
      'Ages 5–9',
    );
  });

  it('lists the checked facts that belong to the kind, in page order', () => {
    const place = buildListing({
      activity: { kind: 'place', facts: { shade: false, toilets: true, kids_menu: true } },
    });

    expect(checkedFacts(place)).toEqual([
      { key: 'toilets', present: true },
      { key: 'shade', present: false },
    ]);
  });

  it('formats the check date in Hong Kong time', () => {
    expect(formatMonthYear('en', '2026-10-31T17:00:00Z')).toBe('November 2026');
    expect(formatMonthYear('zh-HK', '2026-11-02T00:00:00Z')).toBe('2026年11月');
    expect(formatMonthYear('en', 'not a date')).toBeNull();
  });
});

describe('prices by kind', () => {
  it('works out a per-class price only for classes', () => {
    const term = buildPricing({ pricingType: 'per_sessions', amount: 1000, sessionsCount: 10 });

    expect(classPriceEquivalent(term, 'class')).toBe(100);
    expect(classPriceEquivalent(term, 'camp')).toBeNull();
  });

  it('shows a free place as free', () => {
    const place = buildListing({
      activity: { kind: 'place' },
      pricing: buildPricing({ pricingType: 'free', amount: 0 }),
      schedule: null,
    });

    expect(formatListingPriceSummary('en', place)).toMatch(/free/i);
  });
});

describe('landing pages by kind', () => {
  it('sums up ages, days, and prices over classes only', () => {
    const facts = landingFacts(
      'en',
      [
        buildListing({ activity: { ageMin: 4, ageMax: 7 } }),
        buildListing({ activity: { id: 'all-ages', ageMin: 0, ageMax: 99 } }),
        buildListing({
          activity: { id: 'park', kind: 'place', ageMin: 1, ageMax: 12 },
          pricing: buildPricing({ amount: 999 }),
        }),
      ],
      pageCopy,
    );

    expect(facts.ages).toBe('4 to 7 years');
    expect(facts.prices).toBe('HK$180');
  });

  it('counts the listings, the parent checks, and the last update', () => {
    const listings = [
      buildListing({ organization: { parentVerified: true, updatedAt: '2026-11-02T00:00:00Z' } }),
      buildListing({ activity: { id: 'act-2' }, organization: { updatedAt: '2026-09-01T00:00:00Z' } }),
    ];

    expect(landingCoverage('en', listings, pageCopy)).toBe(
      '2 listings. 1 checked by a local parent. Last updated November 2026.',
    );
    expect(landingCoverage('en', listings.slice(1), pageCopy)).toBe(
      '1 listings. Last updated September 2026.',
    );
    expect(landingCoverage('en', [], pageCopy)).toBeNull();
  });
});

describe('activity page data by kind', () => {
  const place = buildListing({
    activity: { kind: 'place', categoryName: 'Playground' },
    pricing: buildPricing({ pricingType: 'free', amount: 0 }),
    schedule: null,
  });

  it('describes a free place as a free attraction, not a course', () => {
    const data = activityStructuredData('en', place, [], 'https://example.com/en/activity/x/');

    expect(data).toMatchObject({ '@type': 'TouristAttraction', isAccessibleForFree: true });
    expect(data).not.toHaveProperty('hasCourseInstance');
  });

  it('links a place breadcrumb to the places page', () => {
    const items = activityBreadcrumbItems(
      'en',
      place,
      { homeLabel: 'Home', searchLabel: 'Activities' },
      ['places'],
    );

    expect(items[2]).toEqual({ label: pageCopy.kindPages.places, href: '/en/activities/places/' });
  });
});
