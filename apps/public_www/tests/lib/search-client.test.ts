import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  buildActivitySearchRequest,
  fetchActivitySearch,
} from '@/lib/activities/search-client';

const envKeys = [
  'NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED',
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
    process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL = 'https://siutindei.com';
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
    expect(url).toBe('https://siutindei.com/v1/activities/search?limit=10');
    expect(init.headers).toMatchObject({
      'x-api-key': 'key',
      'x-device-attestation': 'token',
    });
  });

  it('throws when the live search API is not configured', async () => {
    process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED = 'false';
    delete process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL;

    await expect(fetchActivitySearch({ limit: 10 })).rejects.toThrow(
      'Search API is not configured.',
    );
  });
});
