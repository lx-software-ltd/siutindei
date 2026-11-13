import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  CATALOGUE_SNAPSHOT_PATH_ENV,
  CATALOGUE_SNAPSHOT_REQUIRED_ENV,
  EXPORT_PLACEHOLDER_ID,
  LANDING_PAGE_MIN_ACTIVITIES,
  cardListing,
  catalogueActivityIds,
  catalogueActivityParams,
  catalogueCategories,
  catalogueCategoryParams,
  catalogueListing,
  catalogueKindPages,
  catalogueListings,
  catalogueTopicPages,
  clearCatalogueCacheForTests,
  landingTypeIdForListing,
  latestUpdate,
} from '@/lib/activities/catalogue-snapshot';

interface FixtureRow {
  activity: { id: string; category_id: string; category_root_id?: string; kind?: string };
  organization: { status?: string; updated_at?: string };
  [key: string]: unknown;
}

const fixtureRows = (
  JSON.parse(
    readFileSync(join(process.cwd(), 'tests/fixtures/catalogue-snapshot.json'), 'utf8'),
  ) as { items: FixtureRow[] }
).items;
const stagingFixtureSynced = existsSync(
  join(process.cwd(), 'public/fixtures/activity_search_staging.json'),
);

function categoryRows(categoryId: string, count: number): FixtureRow[] {
  const seen = new Set<string>();
  const rows: FixtureRow[] = [];
  for (const row of fixtureRows) {
    if (row.activity.category_id !== categoryId || seen.has(row.activity.id)) {
      continue;
    }
    seen.add(row.activity.id);
    rows.push(structuredClone(row));
    if (rows.length === count) {
      break;
    }
  }
  return rows;
}

function writeSnapshot(items: readonly unknown[], schemaVersion = 1): string {
  const dir = mkdtempSync(join(tmpdir(), 'catalogue-snapshot-'));
  const filePath = join(dir, 'snapshot.json');
  writeFileSync(
    filePath,
    JSON.stringify({ schema_version: schemaVersion, generated_at: '2026-11-13T00:00:00Z', items }),
  );
  return filePath;
}

const [firstCategory, secondCategory] = [
  ...new Set(fixtureRows.map((row) => row.activity.category_id)),
];

describe('catalogue snapshot', () => {
  beforeEach(() => {
    vi.stubEnv('NEXT_PUBLIC_SEARCH_AREA_SCOPE', '');
    vi.stubEnv('NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED', 'false');
    vi.stubEnv(CATALOGUE_SNAPSHOT_REQUIRED_ENV, '');
    clearCatalogueCacheForTests();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    clearCatalogueCacheForTests();
  });

  it('reads activities from the snapshot file and exports one page per locale', () => {
    const rows = [
      ...categoryRows(firstCategory, LANDING_PAGE_MIN_ACTIVITIES),
      ...categoryRows(secondCategory, LANDING_PAGE_MIN_ACTIVITIES - 1),
    ];
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, writeSnapshot(rows));

    const ids = catalogueActivityIds();
    expect(new Set(ids)).toEqual(new Set(rows.map((row) => row.activity.id)));
    expect(catalogueActivityParams()).toHaveLength(ids.length * 2);
    expect(catalogueListing(rows[0].activity.id)?.activity.id).toBe(rows[0].activity.id);
    expect(catalogueListing('missing')).toBeNull();
  });

  it('gives a landing page only to activity types with enough activities', () => {
    const rows = [
      ...categoryRows(firstCategory, LANDING_PAGE_MIN_ACTIVITIES),
      ...categoryRows(secondCategory, LANDING_PAGE_MIN_ACTIVITIES - 1),
    ];
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, writeSnapshot(rows));

    const topics = catalogueTopicPages();
    expect(topics.map((category) => category.categoryId)).toEqual([firstCategory]);
    expect(catalogueKindPages().map((category) => category.typeId)).toEqual(['classes']);
    expect(catalogueCategories().map((category) => category.typeId)).toEqual([
      'classes',
      topics[0].typeId,
    ]);
    expect(catalogueCategoryParams()).toEqual([
      { locale: 'en', category: 'classes' },
      { locale: 'en', category: topics[0].typeId },
      { locale: 'zh-HK', category: 'classes' },
      { locale: 'zh-HK', category: topics[0].typeId },
    ]);
  });

  it('drops ended sessions and lists camps by their next start', () => {
    const camps = categoryRows(firstCategory, LANDING_PAGE_MIN_ACTIVITIES + 1);
    const sessions: ReadonlyArray<[string, string]> = [
      ['2099-08-03', '2099-08-07'],
      ['2099-07-06', '2099-07-10'],
      ['2099-07-20', '2099-07-24'],
      ['2020-07-20', '2020-07-24'],
    ];
    camps.forEach((row, index) => {
      row.activity.kind = 'camp';
      const [startsOn, endsOn] = sessions[index];
      row.schedule = { ...(row.schedule as object), starts_on: startsOn, ends_on: endsOn };
    });
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, writeSnapshot(camps));

    expect(catalogueListing(camps[3].activity.id)).toBeNull();
    const [page] = catalogueKindPages();
    expect(page.typeId).toBe('camps');
    expect(page.listings.map((listing) => listing.activity.id)).toEqual([
      camps[1].activity.id,
      camps[2].activity.id,
      camps[0].activity.id,
    ]);
  });

  it('files a leaf under its root topic and keeps places off topic pages', () => {
    const classes = categoryRows(firstCategory, LANDING_PAGE_MIN_ACTIVITIES);
    const places = categoryRows(secondCategory, LANDING_PAGE_MIN_ACTIVITIES);
    for (const row of classes) {
      row.activity.category_root_id = firstCategory;
      row.activity.category_id = 'c1111111-1111-1111-1111-111111119999';
    }
    for (const row of places) {
      row.activity.kind = 'place';
    }
    const rows = [...classes, ...places];
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, writeSnapshot(rows));

    const [topic] = catalogueTopicPages();
    expect(topic.categoryId).toBe(firstCategory);
    expect(topic.listings.map((listing) => listing.activity.kind)).toEqual(
      classes.map(() => 'class'),
    );
    expect(catalogueKindPages().map((page) => [page.typeId, page.listings.length])).toEqual([
      ['classes', LANDING_PAGE_MIN_ACTIVITIES],
      ['places', LANDING_PAGE_MIN_ACTIVITIES],
    ]);

    const place = catalogueListings().find((listing) => listing.activity.kind === 'place');
    const leafClass = catalogueListings().find((listing) => listing.activity.kind === 'class');
    expect(place && landingTypeIdForListing(place)).toBe('places');
    expect(leafClass && landingTypeIdForListing(leafClass)).toBe(topic.typeId);
  });

  it('drops hidden and permanently closed organisations', () => {
    const rows = categoryRows(firstCategory, 2);
    rows[0].organization.status = 'hidden';
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, writeSnapshot(rows));

    expect(catalogueActivityIds()).toEqual([rows[1].activity.id]);
  });

  it('exports only the placeholder when there is no catalogue', () => {
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, '');

    expect(catalogueListings()).toEqual([]);
    expect(catalogueActivityParams()).toEqual([
      { locale: 'en', id: EXPORT_PLACEHOLDER_ID },
      { locale: 'zh-HK', id: EXPORT_PLACEHOLDER_ID },
    ]);
    expect(catalogueCategoryParams().map((param) => param.category)).toEqual([
      EXPORT_PLACEHOLDER_ID,
      EXPORT_PLACEHOLDER_ID,
    ]);
  });

  it('fails the build when the snapshot is required but empty', () => {
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, writeSnapshot([]));
    vi.stubEnv(CATALOGUE_SNAPSHOT_REQUIRED_ENV, 'true');

    expect(() => catalogueListings()).toThrow(/catalogue is empty/);
  });

  it('rejects a snapshot with an unknown schema version', () => {
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, writeSnapshot(categoryRows(firstCategory, 1), 2));

    expect(() => catalogueListings()).toThrow(/Unsupported catalogue snapshot schema 2/);
  });

  it.skipIf(!stagingFixtureSynced)('caps the staging fixture sample when no snapshot is set', () => {
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, '');
    vi.stubEnv('NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED', 'true');

    expect(catalogueListings()).toHaveLength(60);
  });

  it('strips descriptions and contacts from card listings', () => {
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, writeSnapshot(categoryRows(firstCategory, 1)));

    const card = cardListing(catalogueListings()[0]);
    expect(card.activity.description).toBeNull();
    expect(card.organization.description).toBeNull();
    expect(card.organization.contact).toBeNull();
    expect(card.organization.mediaUrls.length).toBeLessThanOrEqual(1);
  });

  it('reports the newest organisation update', () => {
    const rows = categoryRows(firstCategory, 2);
    rows[0].organization.updated_at = '2026-10-01T00:00:00Z';
    rows[1].organization.updated_at = '2026-11-02T00:00:00Z';
    vi.stubEnv(CATALOGUE_SNAPSHOT_PATH_ENV, writeSnapshot(rows));

    expect(latestUpdate(catalogueListings())?.toISOString()).toBe('2026-11-02T00:00:00.000Z');
    expect(latestUpdate([])).toBeNull();
  });
});
