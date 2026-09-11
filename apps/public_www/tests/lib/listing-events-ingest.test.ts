import { afterEach, describe, expect, it, vi } from 'vitest';

import { ingestListingEvents } from '@/lib/analytics/listing-events-ingest';

describe('ingestListingEvents', () => {
  const envKeys = [
    'NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED',
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
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  for (const key of envKeys) {
    original[key] = process.env[key];
  }

  it('no-ops when the search API is not configured', async () => {
    delete process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL;
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await ingestListingEvents([{ event_type: 'search' }]);

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('no-ops in staging fixture mode', async () => {
    process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED = 'true';
    process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL = 'https://siutindei.com';
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await ingestListingEvents([{ event_type: 'listing_view' }]);

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('posts first-party events to /v1/listing-events', async () => {
    process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED = 'false';
    process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL = 'https://siutindei.com';
    process.env.NEXT_PUBLIC_SEARCH_API_KEY = 'key';
    process.env.NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN = 'token';
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);

    await ingestListingEvents([
      {
        event_type: 'listing_view',
        location_id: 'loc-1',
        activity_id: 'act-1',
        client_event_id: 'evt-1',
      },
    ]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect(url).toBe('https://siutindei.com/v1/listing-events');
    expect(init.method).toBe('POST');
    expect(init.headers).toMatchObject({
      'x-api-key': 'key',
      'x-device-attestation': 'token',
    });
    expect(JSON.parse(String(init.body))).toEqual({
      events: [
        {
          event_type: 'listing_view',
          source: 'public_www',
          location_id: 'loc-1',
          activity_id: 'act-1',
          client_event_id: 'evt-1',
        },
      ],
    });
  });
});
