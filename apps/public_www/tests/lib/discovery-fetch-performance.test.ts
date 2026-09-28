import { readFileSync } from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  DISCOVERY_HOME_SEARCH_LIMIT,
  DISCOVERY_LOAD_BUDGET_MS,
  MIN_PUBLIC_LISTINGS,
} from '@/lib/activities/search-limits';
import {
  clearStagingFixtureCacheForTests,
  fetchStagingActivitySearch,
} from '@/lib/activities/staging-search';

const fixturePath = path.resolve(
  __dirname,
  '../../../../shared/fixtures/activity_search_staging.json',
);

const LFS_POINTER_PREFIX = 'version https://git-lfs.github.com/spec/v1';

function readFixtureBody(): string {
  const body = readFileSync(fixturePath, 'utf8');
  if (body.startsWith(LFS_POINTER_PREFIX)) {
    throw new Error(
      'activity_search_staging.json is a Git LFS pointer; run git lfs pull',
    );
  }
  return body;
}

describe('discovery listing load performance', () => {
  beforeAll(() => {
    process.env.NEXT_PUBLIC_SITE_ORIGIN = 'http://localhost:3000';
    const body = readFixtureBody();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('activity_search_staging.json')) {
          return new Response(body, {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );
  });

  afterEach(() => {
    clearStagingFixtureCacheForTests();
  });

  it('returns at least 10 listings within the discovery load budget', async () => {
    await fetchStagingActivitySearch({ limit: 1 });

    const started = performance.now();
    const response = await fetchStagingActivitySearch({
      limit: DISCOVERY_HOME_SEARCH_LIMIT,
    });
    const elapsedMs = performance.now() - started;

    expect(response.items.length).toBeGreaterThanOrEqual(MIN_PUBLIC_LISTINGS);
    expect(elapsedMs).toBeLessThan(DISCOVERY_LOAD_BUDGET_MS);
  });
});
