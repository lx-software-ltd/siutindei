import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  META_DESCRIPTION_MAX_LENGTH,
  activityBreadcrumbItems,
  activityMetaDescription,
  activityStructuredData,
  breadcrumbStructuredData,
  serializeJsonLd,
} from '@/lib/activities/activity-page-data';
import {
  catalogueCategories,
  catalogueListings,
  clearCatalogueCacheForTests,
} from '@/lib/activities/catalogue-snapshot';
import type { ActivityListing } from '@/lib/activities/types';

const copy = { homeLabel: 'Home', searchLabel: 'Activities' };

let listing: ActivityListing;

describe('activity page data', () => {
  beforeAll(() => {
    vi.stubEnv('NEXT_PUBLIC_SEARCH_AREA_SCOPE', '');
    vi.stubEnv('NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED', 'true');
    vi.stubEnv('PUBLIC_WWW_CATALOGUE_SNAPSHOT_PATH', '');
    clearCatalogueCacheForTests();
    listing = catalogueListings()[0];
  });

  afterAll(() => {
    vi.unstubAllEnvs();
    clearCatalogueCacheForTests();
  });

  it('links the breadcrumb through the hub and the landing page when there is one', () => {
    const landingTypeIds = catalogueCategories().map((category) => category.typeId);
    const items = activityBreadcrumbItems('en', listing, copy, landingTypeIds);

    expect(items[0]).toEqual({ label: 'Home', href: '/en/' });
    expect(items[1]).toEqual({ label: 'Activities', href: '/en/activities/' });
    expect(items[2].href).toMatch(/^\/en\/activities\/[^/]+\/$/);
  });

  it('falls back to a type search when the type has no landing page', () => {
    const items = activityBreadcrumbItems('en', listing, copy, []);

    expect(items[2].href).toMatch(/^\/en\/search\//);
  });

  it('writes a meta description from the listing facts within the length limit', () => {
    for (const locale of ['en', 'zh-HK'] as const) {
      const description = activityMetaDescription(locale, listing);
      expect(description.length).toBeGreaterThan(40);
      expect(description.length).toBeLessThanOrEqual(META_DESCRIPTION_MAX_LENGTH);
    }
    expect(activityMetaDescription('en', listing)).toContain(listing.organization.name);
  });

  it('describes the activity as a Course with its provider, ages, and offer', () => {
    const data = activityStructuredData('en', listing, ['https://img.example/a.jpg'], 'https://example.com/en/activity/x/');

    expect(data).toMatchObject({
      '@type': 'Course',
      url: 'https://example.com/en/activity/x/',
      provider: { '@type': 'Organization', name: listing.organization.name },
      image: ['https://img.example/a.jpg'],
    });
    expect((data.hasCourseInstance as unknown[]).length).toBeGreaterThan(0);
  });

  it('numbers breadcrumb list items and makes them absolute', () => {
    const data = breadcrumbStructuredData(
      'https://example.com',
      [{ label: 'Home', href: '/en/' }],
      { label: 'Activities', href: '/en/activities/' },
    );

    expect(data.itemListElement).toEqual([
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://example.com/en/' },
      { '@type': 'ListItem', position: 2, name: 'Activities', item: 'https://example.com/en/activities/' },
    ]);
  });

  it('escapes < so JSON-LD cannot close its script element', () => {
    expect(serializeJsonLd({ name: '</script><b>' })).toBe('{"name":"\\u003c/script>\\u003cb>"}');
  });
});
