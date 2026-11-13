import type { Metadata } from 'next';

import { ActivityDetailPage } from '@/components/pages/activity-detail-page';
import { staticActivityPath } from '@/lib/activities/activity-href';
import {
  activityBreadcrumbItems,
  activityMetaDescription,
  activityStructuredData,
  breadcrumbStructuredData,
  serializeJsonLd,
} from '@/lib/activities/activity-page-data';
import {
  catalogueActivityParams,
  catalogueCategories,
  catalogueListing,
} from '@/lib/activities/catalogue-snapshot';
import { listingImageUrls, listingOrgName, listingTitle } from '@/lib/activities/listing-utils';
import { resolveLocalePageContext } from '@/lib/locale-page';
import { ROUTES } from '@/lib/routes';
import { buildLocalizedMetadata, getSiteOrigin } from '@/lib/seo';
import { getSiteConfig } from '@/lib/site-config';

interface ActivityIdRouteProps {
  params: Promise<{ locale: string; id: string }>;
}

export const dynamicParams = false;

export function generateStaticParams() {
  return catalogueActivityParams();
}

export async function generateMetadata({ params }: ActivityIdRouteProps): Promise<Metadata> {
  const { locale: localeParam, id } = await params;
  const { locale, content } = await resolveLocalePageContext(
    Promise.resolve({ locale: localeParam }),
  );
  const { siteName } = getSiteConfig();
  const listing = catalogueListing(id);
  if (!listing) {
    return buildLocalizedMetadata({
      locale,
      path: ROUTES.activity,
      title: content.seo.activityDetail.title,
      description: content.seo.activityDetail.description,
      siteName,
      robots: { index: false, follow: false },
    });
  }
  const image = listingImageUrls(listing)[0];
  const title = `${listingTitle(locale, listing)} · ${listingOrgName(locale, listing)}`;
  return buildLocalizedMetadata({
    locale,
    path: `${ROUTES.activity}/${id}`,
    title,
    description: activityMetaDescription(locale, listing),
    siteName,
    socialImage: image
      ? { url: image, alt: title }
      : { url: content.seo.defaultSocialImage, alt: content.seo.defaultSocialImageAlt },
  });
}

export default async function StaticActivityPage({ params }: ActivityIdRouteProps) {
  const { locale: localeParam, id } = await params;
  const { locale, content } = await resolveLocalePageContext(
    Promise.resolve({ locale: localeParam }),
  );
  const listing = catalogueListing(id);
  const landingTypeIds = catalogueCategories().map((category) => category.typeId);
  if (!listing) {
    return (
      <ActivityDetailPage
        locale={locale}
        activityId={id}
        copy={content.activityDetail}
        landingTypeIds={landingTypeIds}
      />
    );
  }

  const siteOrigin = getSiteOrigin();
  const pagePath = staticActivityPath(locale, id);
  const pageUrl = new URL(pagePath, siteOrigin).toString();
  const title = listingTitle(locale, listing);
  const course = activityStructuredData(locale, listing, listingImageUrls(listing), pageUrl);
  const breadcrumbs = breadcrumbStructuredData(
    siteOrigin,
    activityBreadcrumbItems(locale, listing, content.activityDetail, landingTypeIds),
    { label: title, href: pagePath },
  );

  return (
    <>
      <script type="application/ld+json">{serializeJsonLd(course)}</script>
      <script type="application/ld+json">{serializeJsonLd(breadcrumbs)}</script>
      <ActivityDetailPage
        locale={locale}
        activityId={id}
        copy={content.activityDetail}
        initialListing={listing}
        landingTypeIds={landingTypeIds}
      />
    </>
  );
}
