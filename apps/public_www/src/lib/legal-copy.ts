import enLegal from '@/content/legal/en.json';
import zhHKLegal from '@/content/legal/zh-HK.json';
import type { Locale } from '@/content/locales';
import type { LegalContent } from '@/content/types';

const legalByLocale: Record<Locale, LegalContent> = {
  en: enLegal,
  'zh-HK': zhHKLegal,
};

export function getLegalContent(locale: Locale): LegalContent {
  return legalByLocale[locale];
}
