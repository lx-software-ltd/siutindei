import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  catalogueCategories,
  catalogueListings,
  clearCatalogueCacheForTests,
} from '@/lib/activities/catalogue-snapshot';
import { buildLlmsTxt } from '@/lib/llms-txt';
import { SNAPSHOT_FIXTURE } from '../helpers/catalogue-fixture';

describe('llms.txt', () => {
  beforeEach(() => {
    vi.stubEnv('NEXT_PUBLIC_SEARCH_AREA_SCOPE', '');
    vi.stubEnv('NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED', 'false');
    vi.stubEnv('PUBLIC_WWW_CATALOGUE_SNAPSHOT_PATH', '');
    clearCatalogueCacheForTests();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    clearCatalogueCacheForTests();
  });

  it('describes the site and links the about and legal pages without a catalogue', () => {
    const text = buildLlmsTxt('https://example.com', 'Siu Tin Dei');

    expect(text.startsWith('# Siu Tin Dei (小天地)\n\n> ')).toBe(true);
    expect(text).toContain('](https://example.com/en/about/)');
    expect(text).toContain('](https://example.com/zh-HK/about/)');
    expect(text).not.toContain('## Activities');
    expect(text).not.toContain('{placeFull}');
  });

  it('links the hub, every type page, and each activity', () => {
    vi.stubEnv('PUBLIC_WWW_CATALOGUE_SNAPSHOT_PATH', SNAPSHOT_FIXTURE);
    const text = buildLlmsTxt('https://example.com', 'Siu Tin Dei');

    expect(text).toContain(`](https://example.com/en/activities/): ${catalogueListings().length} listings`);
    for (const category of catalogueCategories()) {
      expect(text).toContain(`](https://example.com/en/activities/${category.typeId}/)`);
    }
    for (const listing of catalogueListings()) {
      expect(text).toContain(`](https://example.com/en/activity/${listing.activity.id}/)`);
    }
  });
});
