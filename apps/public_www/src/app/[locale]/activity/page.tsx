import { Suspense } from 'react';

import { ActivityDetailRoute } from '@/components/pages/activity-detail-route';
import { catalogueCategories } from '@/lib/activities/catalogue-snapshot';
import {
  generateLocaleStaticParams,
  type LocaleRouteProps,
  resolveLocalePageContext,
} from '@/lib/locale-page';
import { ROUTES } from '@/lib/routes';
import { buildLocalizedMetadata } from '@/lib/seo';
import { getSiteConfig } from '@/lib/site-config';

export function generateStaticParams() {
  return generateLocaleStaticParams();
}

export async function generateMetadata({ params }: LocaleRouteProps) {
  const { locale, content } = await resolveLocalePageContext(params);
  const { siteName } = getSiteConfig();

  return buildLocalizedMetadata({
    locale,
    path: ROUTES.activity,
    title: content.seo.activityDetail.title,
    description: content.seo.activityDetail.description,
    siteName,
    socialImage: {
      url: content.seo.defaultSocialImage,
      alt: content.seo.defaultSocialImageAlt,
    },
    // One shell for every `?id=`; the activities have their own pages.
    robots: { index: false, follow: true },
  });
}

export default async function ActivityRoutePage({ params }: LocaleRouteProps) {
  const { locale, content } = await resolveLocalePageContext(params);

  return (
    <Suspense fallback={null}>
      <ActivityDetailRoute
        locale={locale}
        copy={content.activityDetail}
        landingTypeIds={catalogueCategories().map((category) => category.typeId)}
      />
    </Suspense>
  );
}
