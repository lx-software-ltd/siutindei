import type { Metadata } from 'next';

import { ActivityDetailPage } from '@/components/pages/activity-detail-page';
import type { Locale } from '@/content/locales';
import {
  getStaticActivityListing,
  listStaticActivityExportParams,
} from '@/lib/activities/static-activity-catalog';
import {
  listingOrgName,
  listingTitle,
  pickTranslation,
} from '@/lib/activities/listing-utils';
import type { ActivityListing } from '@/lib/activities/types';
import { resolveLocalePageContext } from '@/lib/locale-page';
import { buildLocalizedMetadata } from '@/lib/seo';
import { getSiteConfig } from '@/lib/site-config';

interface ActivityIdRouteProps {
  params: Promise<{ locale: string; id: string }>;
}

export const dynamicParams = false;

export function generateStaticParams() {
  return listStaticActivityExportParams();
}

function courseJsonLd(locale: Locale, listing: ActivityListing) {
  const description = pickTranslation(
    locale,
    listing.activity.description ?? '',
    listing.activity.descriptionTranslations,
  );
  return {
    '@context': 'https://schema.org',
    '@type': 'Course',
    name: listingTitle(locale, listing),
    description: description || undefined,
    provider: {
      '@type': 'Organization',
      name: listingOrgName(locale, listing),
    },
    offers: {
      '@type': 'Offer',
      price: listing.pricing.amount,
      priceCurrency: listing.pricing.currency,
    },
  };
}

export async function generateMetadata({
  params,
}: ActivityIdRouteProps): Promise<Metadata> {
  const { locale: localeParam, id } = await params;
  const { locale, content } = await resolveLocalePageContext(
    Promise.resolve({ locale: localeParam }),
  );
  const listing = getStaticActivityListing(id);
  const { siteName } = getSiteConfig();
  const title = listing
    ? listingTitle(locale, listing)
    : content.seo.activityDetail.title;
  const description = listing
    ? pickTranslation(
        locale,
        listing.activity.description ?? content.seo.activityDetail.description,
        listing.activity.descriptionTranslations,
      )
    : content.seo.activityDetail.description;

  return buildLocalizedMetadata({
    locale,
    path: `/activity/${id}`,
    title,
    description,
    siteName,
    socialImage: {
      url: content.seo.defaultSocialImage,
      alt: content.seo.defaultSocialImageAlt,
    },
  });
}

export default async function StaticActivityPage({
  params,
}: ActivityIdRouteProps) {
  const { locale: localeParam, id } = await params;
  const { locale, content } = await resolveLocalePageContext(
    Promise.resolve({ locale: localeParam }),
  );
  const listing = getStaticActivityListing(id);
  if (!listing) {
    return (
      <p className="mx-auto max-w-4xl px-4 py-16 text-center text-ink-700">
        {content.activityDetail.notFoundLabel}
      </p>
    );
  }

  return (
    <>
      <script
        type="application/ld+json"
        data-activity-jsonld={listing.activity.id}
      >
        {JSON.stringify(courseJsonLd(locale, listing))}
      </script>
      <ActivityDetailPage
        locale={locale}
        activityId={listing.activity.id}
        copy={content.activityDetail}
        initialListing={listing}
      />
    </>
  );
}
