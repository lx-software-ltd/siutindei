import { afterEach, describe, expect, it } from 'vitest';

import { buildCspDirectives } from '../../scripts/inject-csp-meta.mjs';

const envKeys = [
  'NEXT_PUBLIC_SITE_ORIGIN',
  'NEXT_PUBLIC_SEARCH_API_BASE_URL',
  'NEXT_PUBLIC_GTM_ID',
  'NEXT_PUBLIC_META_PIXEL_ID',
  'NEXT_PUBLIC_GOOGLE_MAPS_API_KEY',
];

describe('buildCspDirectives search override', () => {
  const original = {};

  afterEach(() => {
    for (const key of envKeys) {
      if (original[key] === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = original[key];
      }
    }
  });

  function rememberEnv() {
    for (const key of envKeys) {
      original[key] = process.env[key];
      delete process.env[key];
    }
  }

  it('keeps connect-src self when search uses the site origin', () => {
    rememberEnv();
    process.env.NEXT_PUBLIC_SITE_ORIGIN = 'https://example.com';

    const policy = buildCspDirectives([]);
    expect(policy).toContain("connect-src 'self'");
    expect(policy).not.toContain('https://example.com');
  });

  it('allows a different local search origin', () => {
    rememberEnv();
    process.env.NEXT_PUBLIC_SITE_ORIGIN = 'http://localhost:3100';
    process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL =
      'https://www-staging.example.com/';

    expect(buildCspDirectives([])).toContain(
      "connect-src 'self' https://www-staging.example.com",
    );
  });
});
