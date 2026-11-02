import { notFound } from 'next/navigation';

import { getContent } from '@/content';
import {
  isValidLocale,
  SUPPORTED_LOCALES,
  type Locale,
} from '@/content/locales';
import type { SiteContent } from '@/content/types';

export type LocaleRouteParams = Promise<{ locale: string }>;

export interface LocaleRouteProps {
  params: LocaleRouteParams;
}

export interface LocalePageContext {
  locale: Locale;
  content: SiteContent;
}

export async function resolveLocalePageContext(
  params: LocaleRouteParams,
): Promise<LocalePageContext> {
  const { locale } = await params;
  if (!isValidLocale(locale)) {
    notFound();
  }

  return {
    locale,
    content: getContent(locale),
  };
}

export function generateLocaleStaticParams() {
  return SUPPORTED_LOCALES.map((locale) => ({ locale }));
}
