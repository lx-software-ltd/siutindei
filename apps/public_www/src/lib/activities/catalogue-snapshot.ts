import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { SUPPORTED_LOCALES, type Locale } from '@/content/locales';
import { stagingScopeAreaIds } from '@/lib/home-wizard/area-scope';
import { homeWizardChoices, type WizardLabels } from '@/lib/home-wizard/choices';
import { getSearchConfig } from '@/lib/site-config';

import { hideImportTemplateCopy } from './description-boilerplate';
import { groupListings } from './group-listings';
import { KIND_PAGES, kindPageForKind } from './kind-pages';
import { TOPIC_KINDS, topicForListing } from './listing-facts';
import { mapActivityListing, type ActivityWireListing } from './map-listing';
import { compareByNextSession, hongKongToday } from './schedule-dates';
import type { ActivityListing, ListingKind } from './types';

/**
 * Build-time catalogue for the pre-rendered activity and landing pages.
 *
 * Production reads the snapshot that `CatalogueSnapshotFunction` writes
 * (`PUBLIC_WWW_CATALOGUE_SNAPSHOT_PATH`). Staging with the fixture on
 * takes a capped sample of the fixture, so its deploy stays short (#828).
 * Without either the catalogue is empty and only placeholder pages are
 * exported, which the build then deletes.
 */

export const CATALOGUE_SNAPSHOT_PATH_ENV = 'PUBLIC_WWW_CATALOGUE_SNAPSHOT_PATH';
export const CATALOGUE_SNAPSHOT_REQUIRED_ENV = 'PUBLIC_WWW_CATALOGUE_SNAPSHOT_REQUIRED';
export const STAGING_CATALOGUE_ACTIVITY_LIMIT = 60;
export const LANDING_PAGE_MIN_ACTIVITIES = 3;

/**
 * Next.js `output: 'export'` rejects an empty `generateStaticParams()`.
 * This id is not a listing; `scripts/prune-export-placeholders.mjs`
 * deletes its pages after export.
 */
export const EXPORT_PLACEHOLDER_ID = '__export_placeholder__';

const SNAPSHOT_SCHEMA_VERSION = 1;

interface CatalogueRow extends ActivityWireListing {
  readonly _sort?: {
    readonly day_of_week_utc: number;
    readonly start_minutes_utc: number;
    readonly schedule_id: string;
  };
}

interface CatalogueFile {
  readonly schema_version?: number;
  readonly items?: readonly CatalogueRow[];
}

/** A landing page: a kind (`classes`, `places`, ...) or a wizard topic. */
export interface CatalogueCategory {
  /** The `/activities/{typeId}` segment: a kind page slug or a wizard topic id. */
  readonly typeId: string;
  readonly pageKind: 'kind' | 'topic';
  /** The kind a kind page lists. */
  readonly listingKind: ListingKind | null;
  /** The wizard topic's category, for a topic page. */
  readonly categoryId: string | null;
  readonly labels: WizardLabels;
  readonly listings: readonly ActivityListing[];
}

let cachedListings: readonly ActivityListing[] | null = null;

export function clearCatalogueCacheForTests(): void {
  cachedListings = null;
}

function snapshotRequired(): boolean {
  const raw = (process.env[CATALOGUE_SNAPSHOT_REQUIRED_ENV] ?? '').trim().toLowerCase();
  return raw === 'true' || raw === '1' || raw === 'yes';
}

function stagingFixturePath(): string {
  return path.resolve(process.cwd(), 'public/fixtures/activity_search_staging.json');
}

function readJson(filePath: string): CatalogueFile {
  return JSON.parse(readFileSync(filePath, 'utf8')) as CatalogueFile;
}

function readSnapshotRows(filePath: string): readonly CatalogueRow[] {
  const parsed = readJson(filePath);
  if (parsed.schema_version !== SNAPSHOT_SCHEMA_VERSION) {
    throw new Error(
      `Unsupported catalogue snapshot schema ${String(parsed.schema_version)} in ${filePath}`,
    );
  }
  return parsed.items ?? [];
}

function fixtureSortKey(row: CatalogueRow): [number, number, string] {
  return [
    row._sort?.day_of_week_utc ?? 0,
    row._sort?.start_minutes_utc ?? 0,
    row._sort?.schedule_id ?? '',
  ];
}

function compareFixtureRows(left: CatalogueRow, right: CatalogueRow): number {
  const [leftDay, leftStart, leftId] = fixtureSortKey(left);
  const [rightDay, rightStart, rightId] = fixtureSortKey(right);
  return leftDay - rightDay || leftStart - rightStart || leftId.localeCompare(rightId);
}

function isPublished(row: CatalogueRow): boolean {
  const status = row.organization.status;
  if (status === 'closed_permanently' || status === 'hidden') {
    return false;
  }
  return row.location.status !== 'permanently_closed';
}

/** A page built before a session ends keeps it until the next build. */
function sessionEndedBefore(row: CatalogueRow, today: string): boolean {
  const endsOn = row.schedule?.ends_on;
  return Boolean(endsOn && endsOn < today);
}

function toListing(row: CatalogueRow): ActivityListing {
  const isTemplate = hideImportTemplateCopy(
    row.organization.description_source,
    row.organization.description,
  );
  return mapActivityListing(
    {
      ...row,
      activity: {
        ...row.activity,
        description: isTemplate ? null : row.activity.description,
        description_translations: isTemplate ? {} : row.activity.description_translations,
      },
      organization: {
        ...row.organization,
        description: isTemplate ? null : row.organization.description,
      },
    },
    'full',
  );
}

function loadRows(): { rows: readonly CatalogueRow[]; limit: number | null } {
  const snapshotPath = (process.env[CATALOGUE_SNAPSHOT_PATH_ENV] ?? '').trim();
  if (snapshotPath) {
    return { rows: readSnapshotRows(snapshotPath), limit: null };
  }
  if (getSearchConfig().stagingSearchDataEnabled && existsSync(stagingFixturePath())) {
    const rows = [...(readJson(stagingFixturePath()).items ?? [])].sort(compareFixtureRows);
    return { rows, limit: STAGING_CATALOGUE_ACTIVITY_LIMIT };
  }
  return { rows: [], limit: null };
}

/** Every activity of the catalogue in the public area scope, grouped. */
export function catalogueListings(): readonly ActivityListing[] {
  if (cachedListings) {
    return cachedListings;
  }
  const { rows, limit } = loadRows();
  const scope = stagingScopeAreaIds();
  const today = hongKongToday();
  const listings = groupListings(
    rows
      .filter(isPublished)
      .filter((row) => !sessionEndedBefore(row, today))
      .filter((row) => !scope || scope.has(row.location.area_id))
      .map(toListing),
  );
  const capped = limit === null ? listings : listings.slice(0, limit);
  if (capped.length === 0 && snapshotRequired()) {
    throw new Error(
      `${CATALOGUE_SNAPSHOT_REQUIRED_ENV} is set but the catalogue is empty. ` +
        `Set ${CATALOGUE_SNAPSHOT_PATH_ENV} to the downloaded snapshot.`,
    );
  }
  cachedListings = capped;
  return capped;
}

export function catalogueListing(activityId: string): ActivityListing | null {
  return catalogueListings().find((listing) => listing.activity.id === activityId) ?? null;
}

export function catalogueActivityIds(): readonly string[] {
  return catalogueListings().map((listing) => listing.activity.id);
}

export function catalogueActivityParams(): Array<{ locale: Locale; id: string }> {
  const ids = catalogueActivityIds();
  const exported = ids.length > 0 ? ids : [EXPORT_PLACEHOLDER_ID];
  return SUPPORTED_LOCALES.flatMap((locale) => exported.map((id) => ({ locale, id })));
}

function hasEnoughListings(category: CatalogueCategory): boolean {
  return category.listings.length >= LANDING_PAGE_MIN_ACTIVITIES;
}

function kindPageListings(
  listings: readonly ActivityListing[],
  kind: ListingKind,
): readonly ActivityListing[] {
  const matching = listings.filter((listing) => listing.activity.kind === kind);
  if (kind !== 'camp') {
    return matching;
  }
  const today = hongKongToday();
  return [...matching].sort((left, right) => compareByNextSession(left, right, today));
}

/** Kinds with enough listings for a page, in hub order. Camps start soonest first. */
export function catalogueKindPages(): readonly CatalogueCategory[] {
  const listings = catalogueListings();
  return KIND_PAGES.map((page) => ({
    typeId: page.slug,
    pageKind: 'kind' as const,
    listingKind: page.kind,
    categoryId: null,
    labels: page.labels,
    listings: kindPageListings(listings, page.kind),
  })).filter(hasEnoughListings);
}

/** Wizard topics with enough classes and camps for a page, in wizard order. */
export function catalogueTopicPages(): readonly CatalogueCategory[] {
  const listings = catalogueListings().filter((listing) =>
    TOPIC_KINDS.has(listing.activity.kind),
  );
  return homeWizardChoices.activityTypes
    .map((type) => ({
      typeId: type.id,
      pageKind: 'topic' as const,
      listingKind: null,
      categoryId: type.categoryId,
      labels: type.labels,
      listings: listings.filter((listing) => topicForListing(listing)?.id === type.id),
    }))
    .filter(hasEnoughListings);
}

/** Every landing page: kinds first, then topics. */
export function catalogueCategories(): readonly CatalogueCategory[] {
  return [...catalogueKindPages(), ...catalogueTopicPages()];
}

export function catalogueCategory(typeId: string): CatalogueCategory | null {
  return catalogueCategories().find((category) => category.typeId === typeId) ?? null;
}

export function catalogueCategoryParams(): Array<{ locale: Locale; category: string }> {
  const typeIds = catalogueCategories().map((category) => category.typeId);
  const exported = typeIds.length > 0 ? typeIds : [EXPORT_PLACEHOLDER_ID];
  return SUPPORTED_LOCALES.flatMap((locale) =>
    exported.map((category) => ({ locale, category })),
  );
}

/** The landing page an activity's breadcrumb points at: its topic, else its kind. */
export function landingTypeIdForListing(listing: ActivityListing): string | null {
  const pages = new Set(catalogueCategories().map((category) => category.typeId));
  const topic = TOPIC_KINDS.has(listing.activity.kind) ? topicForListing(listing) : null;
  if (topic && pages.has(topic.id)) {
    return topic.id;
  }
  const kindPage = kindPageForKind(listing.activity.kind);
  return kindPage && pages.has(kindPage.slug) ? kindPage.slug : null;
}

/** The fields a card shows, so list pages do not ship every description. */
export function cardListing(listing: ActivityListing): ActivityListing {
  return {
    ...listing,
    activity: { ...listing.activity, description: null, descriptionTranslations: {} },
    organization: {
      ...listing.organization,
      description: null,
      descriptionTranslations: {},
      mediaUrls: listing.organization.mediaUrls.slice(0, 1),
      placeId: null,
      contact: null,
      reviews: [],
    },
  };
}

/** The newest `updated_at` among the listings, for the sitemap. */
export function latestUpdate(listings: readonly ActivityListing[]): Date | null {
  let latest: number | null = null;
  for (const listing of listings) {
    const value = listing.organization.updatedAt;
    const time = value ? Date.parse(value) : Number.NaN;
    if (Number.isFinite(time) && (latest === null || time > latest)) {
      latest = time;
    }
  }
  return latest === null ? null : new Date(latest);
}
