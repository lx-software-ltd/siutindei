import { readFileSync } from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

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

describe('fetchStagingActivitySearch', () => {
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

  it('returns at least 3000 listings without filters', async () => {
    const response = await fetchStagingActivitySearch({ limit: 5000 });
    expect(response.items.length).toBeGreaterThanOrEqual(3000);
  });

  it('filters by wizard category and age', async () => {
    const response = await fetchStagingActivitySearch({
      age: 4,
      categoryIds: ['c1111111-1111-1111-1111-111111111201'],
      limit: 20,
    });
    expect(response.items.length).toBe(20);
    for (const item of response.items) {
      expect(item.activity.categoryId).toBe(
        'c1111111-1111-1111-1111-111111111201',
      );
      expect(item.activity.ageMin).toBeLessThanOrEqual(4);
      expect(item.activity.ageMax).toBeGreaterThanOrEqual(4);
      expect(item.schedule.languages).toEqual(['en']);
    }
  });
});
