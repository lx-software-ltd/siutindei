import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
  DEFAULT_PAGE_PATHS,
  FIXTURE_ACTIVITY_ID,
  STATIC_COLLECT_ORIGIN,
  buildRuntimeConfig,
  collectUrl,
  parsePagePaths,
} from '../../scripts/lighthouse-runtime-config.mjs';

const baseConfig = JSON.parse(
  readFileSync(join(process.cwd(), '.lighthouserc.json'), 'utf8'),
);

describe('parsePagePaths', () => {
  it('uses the locale pages when the input is empty', () => {
    expect(DEFAULT_PAGE_PATHS).toEqual([
      '/en/',
      '/zh-HK/',
      '/en/activities/',
      '/en/activities/arts/',
      `/en/activity/${FIXTURE_ACTIVITY_ID}/`,
    ]);
    expect(parsePagePaths('')).toEqual(DEFAULT_PAGE_PATHS);
    expect(parsePagePaths('  \n  ')).toEqual(DEFAULT_PAGE_PATHS);
  });

  it('splits comma and newline lists', () => {
    expect(parsePagePaths('/en/,\n/zh-HK/')).toEqual(['/en/', '/zh-HK/']);
  });
});

describe('collectUrl', () => {
  it('maps the locale-redirect root to /en/', () => {
    expect(collectUrl('/')).toBe(`${STATIC_COLLECT_ORIGIN}/en/`);
  });

  it('keeps locale paths on the static collect origin', () => {
    expect(collectUrl('/zh-HK/')).toBe(`${STATIC_COLLECT_ORIGIN}/zh-HK/`);
    expect(collectUrl('en/search/')).toBe(
      `${STATIC_COLLECT_ORIGIN}/en/search/`,
    );
  });

  it('passes through absolute URLs', () => {
    expect(collectUrl('https://www-staging.siutindei.com/en/')).toBe(
      'https://www-staging.siutindei.com/en/',
    );
  });
});

describe('buildRuntimeConfig', () => {
  it('writes the default collect URLs when page_paths is empty', () => {
    const { urls, config } = buildRuntimeConfig({
      pagePathsRaw: '',
      stagingOrigin: 'https://www-staging.siutindei.com',
      bypassSecret: 'unused',
      baseConfig,
    });

    expect(urls).toEqual(
      DEFAULT_PAGE_PATHS.map((path) => `${STATIC_COLLECT_ORIGIN}${path}`),
    );
    expect(config.ci.collect.url).toEqual(urls);
    expect(config.ci.collect.settings?.extraHeaders).toBeUndefined();
    expect(config.ci.collect.settings.throttlingMethod).toBe('devtools');
  });

  it('adds the staging bypass header only for live staging URLs', () => {
    const { config } = buildRuntimeConfig({
      pagePathsRaw: 'https://www-staging.siutindei.com/en/',
      stagingOrigin: 'https://www-staging.siutindei.com',
      bypassSecret: 'bypass-secret',
      baseConfig,
    });

    expect(config.ci.collect.settings.extraHeaders).toBe(
      JSON.stringify({ 'x-staging-bypass': 'bypass-secret' }),
    );
    expect(config.ci.collect.settings.throttlingMethod).toBe('devtools');
  });

  it('refuses a staging audit without the bypass secret', () => {
    expect(() =>
      buildRuntimeConfig({
        pagePathsRaw: 'https://www-staging.siutindei.com/en/',
        stagingOrigin: 'https://www-staging.siutindei.com',
        bypassSecret: '  ',
        baseConfig,
      }),
    ).toThrow(/STAGING_BYPASS_SECRET/);
  });
});
