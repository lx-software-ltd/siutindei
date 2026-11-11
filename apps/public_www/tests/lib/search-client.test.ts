import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  buildActivitySearchRequest,
  fetchActivitySearch,
} from '@/lib/activities/search-client';

const envKeys = [
  'NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED',
  'NEXT_PUBLIC_SITE_ORIGIN',
  'NEXT_PUBLIC_SEARCH_API_BASE_URL',
  'NEXT_PUBLIC_SEARCH_API_KEY',
  'NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN',
] as const;

describe('buildActivitySearchRequest', () => {
  it('maps search params to the public search API query string', () => {
    const { url, headers } = buildActivitySearchRequest(
      {
        age: 5,
        areaId: 'a1111111-1111-1111-1111-111111111102',
        activityId: 'act-1',
        categoryIds: ['c1111111-1111-1111-1111-111111111101'],
        cursor: 'cursor-token',
        limit: 10,
      },
      {
        apiBaseUrl: 'https://siutindei.com',
        apiKey: 'api-key',
        attestationToken: 'attest',
      },
    );

    const parsed = new URL(url);
    expect(parsed.origin).toBe('https://siutindei.com');
    expect(parsed.pathname).toBe('/v1/activities/search');
    expect(parsed.searchParams.get('age')).toBe('5');
    expect(parsed.searchParams.get('area_id')).toBe(
      'a1111111-1111-1111-1111-111111111102',
    );
    expect(parsed.searchParams.get('activity_id')).toBe('act-1');
    expect(parsed.searchParams.get('cursor')).toBe('cursor-token');
    expect(parsed.searchParams.get('limit')).toBe('10');
    expect(parsed.searchParams.get('include_incomplete')).toBe('true');
    expect(parsed.searchParams.getAll('category_id')).toEqual([
      'c1111111-1111-1111-1111-111111111101',
    ]);
    expect(headers).toMatchObject({
      Accept: 'application/json',
      'x-api-key': 'api-key',
      'x-device-attestation': 'attest',
    });
  });
});

describe('buildActivitySearchRequest refinements', () => {
  const config = { apiBaseUrl: 'https://siutindei.com', apiKey: 'api-key', attestationToken: '' };

  it('sends organiser, day, price, sort, and total parameters', () => {
    const { url } = buildActivitySearchRequest(
      {
        organizationIds: ['org-1', 'org-2'],
        pricingType: 'free',
        languages: ['yue'],
        daysOfWeekHkt: [0, 6],
        freeTrial: true,
        classPriceMax: 250,
        sort: 'price',
        includeTotal: true,
      },
      config,
    );

    const parsed = new URL(url).searchParams;
    expect(parsed.getAll('organization_id')).toEqual(['org-1', 'org-2']);
    expect(parsed.get('pricing_type')).toBe('free');
    expect(parsed.getAll('language')).toEqual(['yue']);
    expect(parsed.getAll('day_of_week_hkt')).toEqual(['0', '6']);
    expect(parsed.get('free_trial')).toBe('true');
    expect(parsed.get('class_price_max')).toBe('250');
    expect(parsed.get('sort')).toBe('price');
    expect(parsed.get('include_total')).toBe('true');
  });

  it('asks for the total only on the first page and omits the default sort', () => {
    const { url } = buildActivitySearchRequest(
      { cursor: 'next', includeTotal: true, sort: 'time' },
      config,
    );

    const parsed = new URL(url).searchParams;
    expect(parsed.has('include_total')).toBe(false);
    expect(parsed.has('sort')).toBe(false);
  });
});

describe('fetchActivitySearch live API integration', () => {
  const original: Record<string, string | undefined> = {};

  afterEach(() => {
    for (const key of envKeys) {
      if (original[key] === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = original[key];
      }
    }
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  for (const key of envKeys) {
    original[key] = process.env[key];
  }

  it('calls GET /v1/activities/search with auth headers when configured', async () => {
    process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED = 'false';
    process.env.NEXT_PUBLIC_SITE_ORIGIN = 'https://siutindei.com';
    delete process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL;
    process.env.NEXT_PUBLIC_SEARCH_API_KEY = 'key';
    process.env.NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN = 'token';

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [],
        next_cursor: null,
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await fetchActivitySearch({ limit: 10 });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      'https://siutindei.com/v1/activities/search?include_incomplete=true&limit=10',
    );
    expect(init.headers).toMatchObject({
      'x-api-key': 'key',
      'x-device-attestation': 'token',
    });
  });

  it('throws when the live search API is not configured', async () => {
    process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED = 'false';
    delete process.env.NEXT_PUBLIC_SITE_ORIGIN;

    await expect(fetchActivitySearch({ limit: 10 })).rejects.toThrow(
      'Search API is not configured.',
    );
  });

  it('uses a local search base URL override', async () => {
    process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED = 'false';
    process.env.NEXT_PUBLIC_SITE_ORIGIN = 'http://localhost:3100';
    process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL =
      'https://www-staging.example.com';
    process.env.NEXT_PUBLIC_SEARCH_API_KEY = 'key';
    process.env.NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN = 'token';

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], next_cursor: null }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await fetchActivitySearch({ limit: 1 });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      'https://www-staging.example.com/v1/activities/search?include_incomplete=true&limit=1',
    );
  });
});
