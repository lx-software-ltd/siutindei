import { readFileSync } from 'node:fs';
import path from 'node:path';

import { SUPPORTED_LOCALES, type Locale } from '@/content/locales';

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
  const parsed = JSON.parse(readFileSync(fixturePath(), 'utf8')) as FixtureFile;
  const listings = new Map<string, ActivityListing>();
  for (const item of parsed.items) {
    const isTemplate = item.organization.description_source === 'template';
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

export function listStaticActivityParams(): Array<{
  locale: Locale;
  id: string;
}> {
  const ids = [...loadListings().keys()];
  return SUPPORTED_LOCALES.flatMap((locale) =>
    ids.map((id) => ({ locale, id })),
  );
}

export function getStaticActivityListing(
  activityId: string,
): ActivityListing | null {
  return loadListings().get(activityId) ?? null;
}
