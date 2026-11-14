import Link from 'next/link';

import { CategoryLinkNav } from '@/components/shared/category-link-nav';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { formatContentTemplate } from '@/content/content-field-utils';
import { staticActivityPath } from '@/lib/activities/activity-href';
import { catalogueListings } from '@/lib/activities/catalogue-snapshot';
import { catalogueScopePlace, categoryLinkGroups } from '@/lib/activities/landing-page-data';
import { listingOrgName, listingTitle, sortListingsForDiscovery } from '@/lib/activities/listing-utils';
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
  const featured = sortListingsForDiscovery(listings).slice(0, HOME_ACTIVITY_LINK_LIMIT);

  return (
    <section aria-labelledby="home-catalogue-heading" className="border-t border-brand-100 py-10">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 id="home-catalogue-heading" className="text-2xl font-bold text-ink-900">
          {formatContentTemplate(copy.hubHeadingTemplate, { ...place })}
        </h2>
        {categoryLinkGroups(locale, copy).map((group) => (
          <CategoryLinkNav
            key={group.id}
            group={group}
            countTemplate={copy.activityCountTemplate}
            headingLevel="h3"
            className="mt-6"
          />
        ))}
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
