import { AboutPage } from '@/components/sections/about-page';
import { breadcrumbStructuredData, serializeJsonLd } from '@/lib/activities/activity-page-data';
import { catalogueScopePlace } from '@/lib/activities/landing-page-data';
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

export async function generateMetadata({ params }: LocaleRouteProps) {
  const { locale, content } = await resolveLocalePageContext(params);
  const { siteName } = getSiteConfig();

  return buildLocalizedMetadata({
    locale,
    path: ROUTES.about,
    title: content.seo.about.title,
    description: content.seo.about.description,
    siteName,
    socialImage: {
      url: content.seo.defaultSocialImage,
      alt: content.seo.defaultSocialImageAlt,
    },
  });
}

export default async function AboutRoutePage({ params }: LocaleRouteProps) {
  const { locale, content } = await resolveLocalePageContext(params);
  const { contact } = getSiteConfig();
  const siteOrigin = getSiteOrigin();
  const pagePath = localizePath(ROUTES.about, locale);
  const { placeFull } = catalogueScopePlace(locale, content.discovery);

  return (
    <>
      <script type="application/ld+json">
        {serializeJsonLd({
          '@context': 'https://schema.org',
          '@type': 'AboutPage',
          url: new URL(pagePath, siteOrigin).toString(),
          name: content.pages.about.title,
          inLanguage: locale,
          about: { '@id': `${siteOrigin}/#organization` },
          isPartOf: { '@id': `${siteOrigin}/#website` },
        })}
      </script>
      <script type="application/ld+json">
        {serializeJsonLd(
          breadcrumbStructuredData(
            siteOrigin,
            [{ label: content.activityDetail.homeLabel, href: localizePath(ROUTES.home, locale) }],
            { label: content.pages.about.title, href: pagePath },
          ),
        )}
      </script>
      <AboutPage
        content={content.pages.about}
        contactEmail={contact.email}
        placeFull={placeFull}
      />
    </>
  );
}
