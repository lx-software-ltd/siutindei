import { LegalPage } from '@/components/sections/legal-page';
import { getLegalContent } from '@/lib/legal-copy';
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
    path: ROUTES.terms,
    title: content.seo.terms.title,
    description: content.seo.terms.description,
    siteName,
    socialImage: {
      url: content.seo.defaultSocialImage,
      alt: content.seo.defaultSocialImageAlt,
    },
  });
}

export default async function TermsRoutePage({ params }: LocaleRouteProps) {
  const { locale } = await resolveLocalePageContext(params);
  const legal = getLegalContent(locale);

  return (
    <LegalPage
      document={legal.terms}
      lastUpdatedLabel={legal.lastUpdatedLabel}
      lastUpdated={legal.lastUpdated}
      onThisPageLabel={legal.onThisPageLabel}
    />
  );
}
