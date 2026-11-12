import { AboutPage } from '@/components/sections/about-page';
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
  const { content } = await resolveLocalePageContext(params);
  const { contact } = getSiteConfig();

  return (
    <AboutPage
      content={content.pages.about}
      contactEmail={contact.email}
    />
  );
}
