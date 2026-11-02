import enContent from './en.json';
import zhHKContent from './zh-HK.json';
import enLegal from './legal/en.json';
import zhHKLegal from './legal/zh-HK.json';

import {
  DEFAULT_LOCALE,
  isValidLocale,
  type Locale,
} from './locales';
import type { SiteContent } from './types';

export {
  DEFAULT_LOCALE,
  SUPPORTED_LOCALES,
  isValidLocale,
  type Locale,
} from './locales';
export type {
  FeaturesContent,
  FooterContent,
  HeroContent,
  LegalContent,
  NavbarContent,
  PageBodyConfig,
  PageBodyGridConfig,
  PageKey,
  SiteContent,
} from './types';

const contentMap = {
  en: enContent,
  'zh-HK': zhHKContent,
} as const;

const legalMap = {
  en: enLegal,
  'zh-HK': zhHKLegal,
} as const;

export function getContent(locale: string): SiteContent {
  const key: Locale = isValidLocale(locale) ? locale : DEFAULT_LOCALE;
  return {
    ...contentMap[key],
    legal: legalMap[key],
  };
}
