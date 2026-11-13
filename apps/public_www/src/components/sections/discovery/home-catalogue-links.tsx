import Link from 'next/link';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { formatContentTemplate } from '@/content/content-field-utils';
import { categoryLandingPath, staticActivityPath } from '@/lib/activities/activity-href';
import { catalogueCategories, catalogueListings } from '@/lib/activities/catalogue-snapshot';
import { catalogueScopePlace } from '@/lib/activities/landing-page-data';
import { listingOrgName, listingTitle, sortListingsForDiscovery } from '@/lib/activities/listing-utils';
import { labelForLocale } from '@/lib/home-wizard/choices';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

export const HOME_ACTIVITY_LINK_LIMIT = 12;

interface HomeCatalogueLinksProps {
  readonly locale: Locale;
  readonly content: SiteContent;
}

/**
 * Plain links into the pre-rendered catalogue pages, so the home page
 * reaches them without running the search API.
 */
export function HomeCatalogueLinks({ locale, content }: HomeCatalogueLinksProps) {
  const listings = catalogueListings();
  if (listings.length === 0) {
    return null;
  }
  const copy = content.activitiesPage;
  const place = catalogueScopePlace(locale, content.discovery);
  const categories = catalogueCategories();
  const featured = sortListingsForDiscovery(listings).slice(0, HOME_ACTIVITY_LINK_LIMIT);

  return (
    <section aria-labelledby="home-catalogue-heading" className="border-t border-brand-100 py-10">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 id="home-catalogue-heading" className="text-2xl font-bold text-ink-900">
          {formatContentTemplate(copy.hubHeadingTemplate, { ...place })}
        </h2>
        {categories.length > 0 ? (
          <nav aria-labelledby="home-catalogue-types" className="mt-6">
            <h3 id="home-catalogue-types" className="text-lg font-semibold text-ink-900">
              {copy.browseByTypeHeading}
            </h3>
            <ul className="mt-3 flex flex-wrap gap-2">
              {categories.map((category) => (
                <li key={category.typeId}>
                  <Link
                    href={categoryLandingPath(locale, category.typeId)}
                    className="link-unadorned inline-flex min-h-11 items-center gap-2 rounded-full border border-brand-200 bg-white px-4 text-sm font-semibold text-ink-900 hover:bg-brand-50"
                  >
                    {labelForLocale(category.labels, locale)}
                    <span className="font-normal text-ink-700">
                      {formatContentTemplate(copy.activityCountTemplate, {
                        count: category.listings.length,
                      })}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ) : null}
        <h3 className="mt-8 text-lg font-semibold text-ink-900">{copy.homeFeaturedHeading}</h3>
        <ul className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {featured.map((listing) => (
            <li key={listing.activity.id}>
              <Link href={staticActivityPath(locale, listing.activity.id)} className="font-semibold">
                {listingTitle(locale, listing)}
              </Link>
              <span className="text-ink-700"> · {listingOrgName(locale, listing)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-6">
          <Link href={localizePath(ROUTES.activities, locale)} className="font-semibold">
            {formatContentTemplate(copy.homeAllLinkTemplate, { count: listings.length })}
          </Link>
        </p>
      </div>
    </section>
  );
}
