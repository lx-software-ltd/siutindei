import { readFileSync } from 'node:fs';
import path from 'node:path';

import { SUPPORTED_LOCALES, type Locale } from '@/content/locales';

import { hideImportTemplateCopy } from './description-boilerplate';
import {
  mapActivityListing,
  type ActivityWireListing,
} from './map-listing';
import type { ActivityListing } from './types';

interface FixtureActivity extends ActivityWireListing {
  readonly activity: ActivityWireListing['activity'] & { readonly id: string };
  readonly organization: ActivityWireListing['organization'];
}

interface FixtureFile {
  readonly items: readonly FixtureActivity[];
}

let cachedListings: Map<string, ActivityListing> | null = null;

function stagingStaticPagesEnabled(): boolean {
  const raw = (process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED ?? '')
    .trim()
    .toLowerCase();
  return raw === 'true' || raw === '1' || raw === 'yes';
}

function fixturePath(): string {
  return path.resolve(
    process.cwd(),
    '../../shared/fixtures/activity_search_staging.json',
  );
}

function loadListings(): Map<string, ActivityListing> {
  if (cachedListings) {
    return cachedListings;
  }
  if (!stagingStaticPagesEnabled()) {
    cachedListings = new Map();
    return cachedListings;
  }
  const parsed = JSON.parse(readFileSync(fixturePath(), 'utf8')) as FixtureFile;
  const listings = new Map<string, ActivityListing>();
  for (const item of parsed.items) {
    const isTemplate = hideImportTemplateCopy(
      item.organization.description_source,
      item.organization.description,
    );
    const listing = mapActivityListing(
      {
        ...item,
        activity: {
          ...item.activity,
          description: isTemplate ? null : item.activity.description,
          description_translations: isTemplate
            ? {}
            : item.activity.description_translations,
        },
        organization: {
          ...item.organization,
          description: isTemplate ? null : item.organization.description,
        },
      },
      'full',
    );
    if (!listings.has(listing.activity.id)) {
      listings.set(listing.activity.id, listing);
    }
  }
  cachedListings = listings;
  return listings;
}

/**
 * Next.js `output: 'export'` rejects `generateStaticParams()` when it is
 * empty. This id is not a listing. The build deletes the two HTML files
 * after export so they are not published or sitemapped.
 */
export const STATIC_ACTIVITY_EXPORT_PLACEHOLDER_ID = '__export_placeholder__';

export function listStaticActivityParams(): Array<{
  locale: Locale;
  id: string;
}> {
  const ids = [...loadListings().keys()];
  return SUPPORTED_LOCALES.flatMap((locale) =>
    ids.map((id) => ({ locale, id })),
  );
}

export function listStaticActivityExportParams(): Array<{
  locale: Locale;
  id: string;
}> {
  const params = listStaticActivityParams();
  if (params.length > 0) {
    return params;
  }
  return SUPPORTED_LOCALES.map((locale) => ({
    locale,
    id: STATIC_ACTIVITY_EXPORT_PLACEHOLDER_ID,
  }));
}

export function getStaticActivityListing(
  activityId: string,
): ActivityListing | null {
  return loadListings().get(activityId) ?? null;
}
