import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import sitemap from '@/app/sitemap';
import {
  catalogueCategories,
  catalogueListings,
  clearCatalogueCacheForTests,
} from '@/lib/activities/catalogue-snapshot';

function urls(): string[] {
  return sitemap().map((entry) => entry.url);
}

describe('sitemap', () => {
  beforeEach(() => {
    vi.stubEnv('NEXT_PUBLIC_SITE_ORIGIN', 'https://example.com');
    vi.stubEnv('NEXT_PUBLIC_SEARCH_AREA_SCOPE', '');
    vi.stubEnv('PUBLIC_WWW_CATALOGUE_SNAPSHOT_PATH', '');
    clearCatalogueCacheForTests();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    clearCatalogueCacheForTests();
  });

  it('lists the brand pages without the search shell when there is no catalogue', () => {
    vi.stubEnv('NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED', 'false');

    expect(urls()).toEqual([
      'https://example.com/en/',
      'https://example.com/zh-HK/',
      'https://example.com/en/about/',
      'https://example.com/zh-HK/about/',
      'https://example.com/en/privacy/',
      'https://example.com/zh-HK/privacy/',
      'https://example.com/en/terms/',
      'https://example.com/zh-HK/terms/',
    ]);
  });

  it('adds the hub, landing, and activity pages with hreflang alternates', () => {
    vi.stubEnv('NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED', 'true');
    const listing = catalogueListings()[0];
    const category = catalogueCategories()[0];
    const entries = sitemap();

    const activity = entries.find(
      (entry) => entry.url === `https://example.com/en/activity/${listing.activity.id}/`,
    );
    expect(activity?.alternates?.languages).toEqual({
      en: `https://example.com/en/activity/${listing.activity.id}/`,
      'zh-HK': `https://example.com/zh-HK/activity/${listing.activity.id}/`,
      'x-default': `https://example.com/en/activity/${listing.activity.id}/`,
    });
    expect(urls()).toContain('https://example.com/zh-HK/activities/');
    expect(urls()).toContain(`https://example.com/en/activities/${category.typeId}/`);
    expect(entries).toHaveLength(2 * (5 + catalogueCategories().length + catalogueListings().length));
    expect(urls().some((url) => url.includes('/search'))).toBe(false);
  });

  it('dates the legal pages from their last update', () => {
    vi.stubEnv('NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED', 'false');
    const privacy = sitemap().find((entry) => entry.url === 'https://example.com/en/privacy/');
    const about = sitemap().find((entry) => entry.url === 'https://example.com/en/about/');

    expect(privacy?.lastModified).toBeInstanceOf(Date);
    expect(about?.lastModified).toBeUndefined();
  });
});
