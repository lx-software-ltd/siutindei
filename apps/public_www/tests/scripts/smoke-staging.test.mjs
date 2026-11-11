import { describe, expect, it } from 'vitest';

import {
  buildLiveSearchProbe,
  shouldProbeLiveSearch,
} from '../../scripts/smoke-staging.mjs';

describe('shouldProbeLiveSearch', () => {
  it('probes only when staging search is explicitly live', () => {
    expect(shouldProbeLiveSearch('false')).toBe(true);
    expect(shouldProbeLiveSearch('0')).toBe(true);
    expect(shouldProbeLiveSearch('no')).toBe(true);
    expect(shouldProbeLiveSearch('true')).toBe(false);
    expect(shouldProbeLiveSearch('')).toBe(false);
    expect(shouldProbeLiveSearch(undefined)).toBe(false);
  });
});

describe('buildLiveSearchProbe', () => {
  it('requests one result with the website credentials', () => {
    const probe = buildLiveSearchProbe('https://www-staging.example.com/', {
      NEXT_PUBLIC_SEARCH_API_KEY: 'key',
      NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN: 'token',
    });

    expect(probe.url).toBe(
      'https://www-staging.example.com/v1/activities/search?limit=1',
    );
    expect(probe.headers).toEqual({
      accept: 'application/json',
      'x-api-key': 'key',
      'x-device-attestation': 'token',
    });
  });

  it('fails when a credential is missing', () => {
    expect(() =>
      buildLiveSearchProbe('https://www-staging.example.com', {
        NEXT_PUBLIC_SEARCH_API_KEY: 'key',
      }),
    ).toThrow(/NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN/);
  });
});
