import type { MetadataRoute } from 'next';

import legalContent from '@/content/legal/en.json';
import { DEFAULT_LOCALE, SUPPORTED_LOCALES } from '@/content/locales';
import {
  catalogueCategories,
  catalogueListings,
  latestUpdate,
} from '@/lib/activities/catalogue-snapshot';
import { localizePath } from '@/lib/locale-routing';
import { INDEXED_ROUTE_PATHS, ROUTES } from '@/lib/routes';
import { getSiteOrigin } from '@/lib/seo';

export const dynamic = 'force-static';

function parseDate(value: string): Date | null {
  const time = Date.parse(value);
  return Number.isFinite(time) ? new Date(time) : null;
}

function entriesFor(
  siteOrigin: string,
  path: string,
  lastModified: Date | null,
): MetadataRoute.Sitemap {
  const languages = Object.fromEntries([
    ...SUPPORTED_LOCALES.map((locale) => [locale, `${siteOrigin}${localizePath(path, locale)}`]),
    ['x-default', `${siteOrigin}${localizePath(path, DEFAULT_LOCALE)}`],
  ]);
  return SUPPORTED_LOCALES.map((locale) => ({
    url: `${siteOrigin}${localizePath(path, locale)}`,
    ...(lastModified ? { lastModified } : {}),
    alternates: { languages },
  }));
}

export default function sitemap(): MetadataRoute.Sitemap {
  const siteOrigin = getSiteOrigin();
  const listings = catalogueListings();
  const catalogueUpdated = latestUpdate(listings);
  const legalUpdated = parseDate(legalContent.lastUpdated);

  const brandPages = INDEXED_ROUTE_PATHS.filter(
    (path) => path !== ROUTES.activities || listings.length > 0,
  ).flatMap((path) => {
    const lastModified =
      path === ROUTES.privacy || path === ROUTES.terms
        ? legalUpdated
        : path === ROUTES.home || path === ROUTES.activities
          ? catalogueUpdated
          : null;
    return entriesFor(siteOrigin, path, lastModified);
  });
  const landingPages = catalogueCategories().flatMap((category) =>
    entriesFor(siteOrigin, `${ROUTES.activities}/${category.typeId}`, latestUpdate(category.listings)),
  );
  const activityPages = listings.flatMap((listing) =>
    entriesFor(siteOrigin, `${ROUTES.activity}/${listing.activity.id}`, latestUpdate([listing])),
  );
  return [...brandPages, ...landingPages, ...activityPages];
}
