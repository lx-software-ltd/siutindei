import { afterEach, describe, expect, it, vi } from 'vitest';

describe('static activity catalog', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('does not read the fixture when staging static pages are off', async () => {
    vi.stubEnv('NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED', '');
    const catalog = await import('@/lib/activities/static-activity-catalog');

    expect(catalog.listStaticActivityParams()).toEqual([]);
    expect(catalog.listStaticActivityExportParams()).toEqual([
      {
        locale: 'en',
        id: catalog.STATIC_ACTIVITY_EXPORT_PLACEHOLDER_ID,
      },
      {
        locale: 'zh-HK',
        id: catalog.STATIC_ACTIVITY_EXPORT_PLACEHOLDER_ID,
      },
    ]);
    expect(catalog.getStaticActivityListing('any-id')).toBeNull();
  });
});
