import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
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
  catalogueListings,
  clearCatalogueCacheForTests,
  latestUpdate,
} from '@/lib/activities/catalogue-snapshot';

interface FixtureRow {
  activity: { id: string; category_id: string };
  organization: { status?: string; updated_at?: string };
  [key: string]: unknown;
}

const fixtureRows = (
  JSON.parse(
    readFileSync(join(process.cwd(), 'public/fixtures/activity_search_staging.json'), 'utf8'),
  ) as { items: FixtureRow[] }
).items;

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

    const categories = catalogueCategories();
    expect(categories.map((category) => category.categoryId)).toEqual([firstCategory]);
    expect(catalogueCategoryParams()).toEqual([
      { locale: 'en', category: categories[0].typeId },
      { locale: 'zh-HK', category: categories[0].typeId },
    ]);
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

  it('caps the staging fixture sample when no snapshot is set', () => {
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
