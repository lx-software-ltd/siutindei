import { readFileSync } from 'node:fs';
import path from 'node:path';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  clearStagingFixtureCacheForTests,
  fetchStagingActivitySearch,
} from '@/lib/activities/staging-search';

const fixturePath = path.resolve(
  __dirname,
  '../../../../shared/fixtures/activity_search_staging.json',
);

interface FixtureItem {
  activity: { id: string; kind?: string };
  organization: { id: string; parent_verified?: boolean };
  [key: string]: unknown;
}

function eatItem(base: FixtureItem, id: string, verified: boolean): FixtureItem {
  const item = structuredClone(base);
  item.activity.id = id;
  item.activity.kind = 'eat';
  item.organization.id = `org-${id}`;
  item.organization.parent_verified = verified;
  return item;
}

describe('staging search eat rule', () => {
  beforeAll(() => {
    process.env.NEXT_PUBLIC_SITE_ORIGIN = 'http://localhost:3000';
    const fixture = JSON.parse(readFileSync(fixturePath, 'utf8')) as { items: FixtureItem[] };
    const [base] = fixture.items;
    const body = JSON.stringify({
      ...fixture,
      items: [eatItem(base, 'eat-checked', true), eatItem(base, 'eat-unchecked', false)],
    });
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(body, { status: 200 })),
    );
  });

  afterAll(() => {
    clearStagingFixtureCacheForTests();
    vi.unstubAllGlobals();
  });

  it('shows an eat listing only when a parent verified its organiser', async () => {
    const response = await fetchStagingActivitySearch({ kinds: ['eat'], limit: 10 });
    expect(response.items.map((item) => item.activity.id)).toEqual(['eat-checked']);
    const direct = await fetchStagingActivitySearch({ activityId: 'eat-unchecked' });
    expect(direct.items).toEqual([]);
  });
});
