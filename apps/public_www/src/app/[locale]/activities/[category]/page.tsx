import type { Metadata } from 'next';

import { ActivitiesLandingPage } from '@/components/pages/activities-landing-page';
import { formatContentTemplate } from '@/content/content-field-utils';
import { categoryLandingPath } from '@/lib/activities/activity-href';
import { breadcrumbStructuredData, serializeJsonLd } from '@/lib/activities/activity-page-data';
import {
  cardListing,
  catalogueCategories,
  catalogueCategory,
  catalogueCategoryParams,
} from '@/lib/activities/catalogue-snapshot';
import {
  catalogueScopePlace,
  itemListStructuredData,
  landingFacts,
  lowerCategory,
} from '@/lib/activities/landing-page-data';
import { buildSearchPageHref } from '@/lib/activities/map-search-url';
import { DEFAULT_SEARCH_FILTERS } from '@/lib/activities/search-params';
import { labelForLocale } from '@/lib/home-wizard/choices';
import { resolveLocalePageContext } from '@/lib/locale-page';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';
import { buildLocalizedMetadata, getSiteOrigin } from '@/lib/seo';
import { getSiteConfig } from '@/lib/site-config';

interface CategoryRouteProps {
  params: Promise<{ locale: string; category: string }>;
}

export const dynamicParams = false;

export function generateStaticParams() {
  return catalogueCategoryParams();
}

async function resolve(params: CategoryRouteProps['params']) {
  const { locale: localeParam, category: typeId } = await params;
  const context = await resolveLocalePageContext(Promise.resolve({ locale: localeParam }));
  const category = catalogueCategory(typeId);
  const label = category ? labelForLocale(category.labels, context.locale) : '';
  const place = catalogueScopePlace(context.locale, context.content.discovery);
  const values = {
    ...place,
    category: label,
    categoryLower: lowerCategory(context.locale, label),
    count: category?.listings.length ?? 0,
  };
  return { ...context, typeId, category, label, values };
}

export async function generateMetadata({ params }: CategoryRouteProps): Promise<Metadata> {
  const { locale, content, typeId, category, values } = await resolve(params);
  const { siteName } = getSiteConfig();
  return buildLocalizedMetadata({
    locale,
    path: `${ROUTES.activities}/${typeId}`,
    title: formatContentTemplate(content.seo.activityCategory.titleTemplate, values),
    description: formatContentTemplate(content.seo.activityCategory.descriptionTemplate, values),
    siteName,
    socialImage: {
      url: content.seo.defaultSocialImage,
      alt: content.seo.defaultSocialImageAlt,
    },
    robots: { index: category !== null, follow: category !== null },
  });
}

export default async function ActivityCategoryPage({ params }: CategoryRouteProps) {
  const { locale, content, typeId, category, label, values } = await resolve(params);
  const copy = content.activitiesPage;
  const listings = category?.listings ?? [];
  const heading = formatContentTemplate(copy.categoryHeadingTemplate, values);
  const siteOrigin = getSiteOrigin();
  const pagePath = categoryLandingPath(locale, typeId);
  const crumbs = [
    { label: content.activityDetail.homeLabel, href: localizePath(ROUTES.home, locale) },
    { label: content.activityDetail.searchLabel, href: localizePath(ROUTES.activities, locale) },
  ];

  return (
    <>
      {category ? (
        <>
          <script type="application/ld+json">
            {serializeJsonLd(itemListStructuredData(siteOrigin, locale, heading, listings))}
          </script>
          <script type="application/ld+json">
            {serializeJsonLd(breadcrumbStructuredData(siteOrigin, crumbs, { label, href: pagePath }))}
          </script>
        </>
      ) : null}
      <ActivitiesLandingPage
        locale={locale}
        content={content}
        heading={heading}
        intro={formatContentTemplate(copy.categoryIntroTemplate, values)}
        breadcrumbs={crumbs}
        facts={landingFacts(locale, listings, copy)}
        categoriesHeading={copy.otherTypesHeading}
        categories={catalogueCategories()
          .filter((entry) => entry.typeId !== typeId)
          .map((entry) => ({
            typeId: entry.typeId,
            label: labelForLocale(entry.labels, locale),
            href: categoryLandingPath(locale, entry.typeId),
            count: entry.listings.length,
          }))}
        listings={listings.map(cardListing)}
        searchHref={buildSearchPageHref(
          locale,
          { ...DEFAULT_SEARCH_FILTERS, activityTypeIds: category ? [typeId] : [] },
          { view: 'list' },
        )}
      />
    </>
  );
}
