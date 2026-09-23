import { afterEach, describe, expect, it } from 'vitest';

import {
  getCopyrightYear,
  getSearchConfig,
  getSiteConfig,
} from '@/lib/site-config';

describe('getCopyrightYear', () => {
  const originalYear = process.env.NEXT_PUBLIC_BUILD_YEAR;

  afterEach(() => {
    if (originalYear === undefined) {
      delete process.env.NEXT_PUBLIC_BUILD_YEAR;
    } else {
      process.env.NEXT_PUBLIC_BUILD_YEAR = originalYear;
    }
  });

  it('uses NEXT_PUBLIC_BUILD_YEAR when valid', () => {
    process.env.NEXT_PUBLIC_BUILD_YEAR = '2030';
    expect(getCopyrightYear()).toBe(2030);
  });

  it('falls back when env is missing or invalid', () => {
    delete process.env.NEXT_PUBLIC_BUILD_YEAR;
    expect(getCopyrightYear()).toBe(new Date().getFullYear());
  });
});

describe('public contacts', () => {
  const envKeys = [
    'NEXT_PUBLIC_EMAIL',
    'NEXT_PUBLIC_WHATSAPP_URL',
  ] as const;
  const original: Record<string, string | undefined> = {};

  afterEach(() => {
    for (const key of envKeys) {
      if (original[key] === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = original[key];
      }
    }
  });

  it('uses the shared defaults when env is unset', () => {
    for (const key of envKeys) {
      original[key] = process.env[key];
      delete process.env[key];
    }

    expect(getSiteConfig().contact).toMatchObject({
      email: 'hello@siutindei.com',
      whatsappUrl: 'https://wa.me/85294460861',
      whatsappDisplay: '+852 9446 0861',
    });
  });

  it('lets NEXT_PUBLIC_EMAIL and NEXT_PUBLIC_WHATSAPP_URL override', () => {
    for (const key of envKeys) {
      original[key] = process.env[key];
    }
    process.env.NEXT_PUBLIC_EMAIL = 'hello@example.com';
    process.env.NEXT_PUBLIC_WHATSAPP_URL = 'https://wa.me/85200000000';

    expect(getSiteConfig().contact).toMatchObject({
      email: 'hello@example.com',
      whatsappUrl: 'https://wa.me/85200000000',
      whatsappDisplay: '+852 9446 0861',
    });
  });
});

describe('getSearchConfig', () => {
  const envKeys = [
    'NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED',
    'NEXT_PUBLIC_SITE_ORIGIN',
    'NEXT_PUBLIC_STAGING_SEARCH_FIXTURE_URL',
    'NEXT_PUBLIC_SEARCH_API_BASE_URL',
    'NEXT_PUBLIC_SEARCH_API_KEY',
    'NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN',
  ] as const;

  const original: Record<string, string | undefined> = {};

  afterEach(() => {
    for (const key of envKeys) {
      if (original[key] === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = original[key];
      }
    }
  });

  it('derives staging fixture URL from site origin when enabled', () => {
    for (const key of envKeys) {
      original[key] = process.env[key];
    }
    process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED = 'true';
    process.env.NEXT_PUBLIC_SITE_ORIGIN = 'http://localhost:3000/';
    delete process.env.NEXT_PUBLIC_STAGING_SEARCH_FIXTURE_URL;
    delete process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL;

    expect(getSearchConfig()).toEqual({
      stagingSearchDataEnabled: true,
      stagingSearchFixtureUrl:
        'http://localhost:3000/fixtures/activity_search_staging.json',
      apiBaseUrl: '',
      apiKey: '',
      attestationToken: '',
    });
  });

  it('prefers explicit fixture URL and live API settings', () => {
    for (const key of envKeys) {
      original[key] = process.env[key];
    }
    process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED = 'false';
    process.env.NEXT_PUBLIC_SITE_ORIGIN = 'https://example.com';
    process.env.NEXT_PUBLIC_STAGING_SEARCH_FIXTURE_URL =
      'https://cdn.example.com/fixture.json';
    process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL = 'https://api.example.com';
    process.env.NEXT_PUBLIC_SEARCH_API_KEY = 'test-key';
    process.env.NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN = 'test-token';

    expect(getSearchConfig()).toEqual({
      stagingSearchDataEnabled: false,
      stagingSearchFixtureUrl: 'https://cdn.example.com/fixture.json',
      apiBaseUrl: 'https://api.example.com',
      apiKey: 'test-key',
      attestationToken: 'test-token',
    });
  });
});
