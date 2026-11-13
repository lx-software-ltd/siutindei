import type { Metadata } from 'next';

import { ActivitiesLandingPage } from '@/components/pages/activities-landing-page';
import { formatContentTemplate } from '@/content/content-field-utils';
import { categoryLandingPath } from '@/lib/activities/activity-href';
import { breadcrumbStructuredData, serializeJsonLd } from '@/lib/activities/activity-page-data';
import {
  cardListing,
  catalogueCategories,
  catalogueListings,
} from '@/lib/activities/catalogue-snapshot';
import {
  catalogueScopePlace,
  itemListStructuredData,
  landingFacts,
} from '@/lib/activities/landing-page-data';
import { buildSearchPageHref } from '@/lib/activities/map-search-url';
import { DEFAULT_SEARCH_FILTERS } from '@/lib/activities/search-params';
import { labelForLocale } from '@/lib/home-wizard/choices';
import {
  generateLocaleStaticParams,
  type LocaleRouteProps,
  resolveLocalePageContext,
} from '@/lib/locale-page';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';
import { buildLocalizedMetadata, getSiteOrigin } from '@/lib/seo';
import { getSiteConfig } from '@/lib/site-config';

export function generateStaticParams() {
  return generateLocaleStaticParams();
}

export async function generateMetadata({ params }: LocaleRouteProps): Promise<Metadata> {
  const { locale, content } = await resolveLocalePageContext(params);
  const { siteName } = getSiteConfig();
  const place = catalogueScopePlace(locale, content.discovery);
  return buildLocalizedMetadata({
    locale,
    path: ROUTES.activities,
    title: formatContentTemplate(content.seo.activities.titleTemplate, { ...place }),
    description: formatContentTemplate(content.seo.activities.descriptionTemplate, { ...place }),
    siteName,
    socialImage: {
      url: content.seo.defaultSocialImage,
      alt: content.seo.defaultSocialImageAlt,
    },
    robots: { index: catalogueListings().length > 0, follow: true },
  });
}

export default async function ActivitiesHubPage({ params }: LocaleRouteProps) {
  const { locale, content } = await resolveLocalePageContext(params);
  const copy = content.activitiesPage;
  const place = catalogueScopePlace(locale, content.discovery);
  const listings = catalogueListings();
  const heading = formatContentTemplate(copy.hubHeadingTemplate, { ...place });
  const siteOrigin = getSiteOrigin();
  const pagePath = localizePath(ROUTES.activities, locale);
  const homeCrumb = {
    label: content.activityDetail.homeLabel,
    href: localizePath(ROUTES.home, locale),
  };

  return (
    <>
      <script type="application/ld+json">
        {serializeJsonLd(itemListStructuredData(siteOrigin, locale, heading, listings))}
      </script>
      <script type="application/ld+json">
        {serializeJsonLd(
          breadcrumbStructuredData(siteOrigin, [homeCrumb], {
            label: content.activityDetail.searchLabel,
            href: pagePath,
          }),
        )}
      </script>
      <ActivitiesLandingPage
        locale={locale}
        content={content}
        heading={heading}
        intro={formatContentTemplate(copy.hubIntro, { ...place })}
        breadcrumbs={[homeCrumb]}
        facts={landingFacts(locale, listings, copy)}
        categoriesHeading={copy.browseByTypeHeading}
        categories={catalogueCategories().map((category) => ({
          typeId: category.typeId,
          label: labelForLocale(category.labels, locale),
          href: categoryLandingPath(locale, category.typeId),
          count: category.listings.length,
        }))}
        listings={listings.map(cardListing)}
        searchHref={buildSearchPageHref(locale, DEFAULT_SEARCH_FILTERS, { view: 'list' })}
      />
    </>
  );
}
