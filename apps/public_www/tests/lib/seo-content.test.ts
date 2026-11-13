import { describe, expect, it } from 'vitest';

import { getContent } from '@/content';
import { SUPPORTED_LOCALES } from '@/content/locales';
import { buildLocalizedMetadata, buildPageTitle } from '@/lib/seo';
import { ROUTES } from '@/lib/routes';

const SITE_NAME = 'Siu Tin Dei';

const PAGE_KEYS = [
  ['about', ROUTES.about],
  ['search', ROUTES.search],
  ['activityDetail', ROUTES.activity],
  ['privacy', ROUTES.privacy],
  ['terms', ROUTES.terms],
] as const;

describe('SEO copy', () => {
  for (const locale of SUPPORTED_LOCALES) {
    const seo = getContent(locale).seo;

    it(`adds the brand once to every ${locale} page title`, () => {
      const titles = PAGE_KEYS.map(([key, path]) => buildPageTitle(seo[key].title, path, SITE_NAME));
      for (const title of titles) {
        expect(title.endsWith(` · ${SITE_NAME}`)).toBe(true);
        expect(title.split(SITE_NAME)).toHaveLength(2);
      }
      expect(new Set(titles).size).toBe(titles.length);
    });

    it(`keeps the ${locale} home description within search snippet length`, () => {
      const { length } = seo.home.description;
      expect(length).toBeGreaterThanOrEqual(locale === 'en' ? 120 : 50);
      expect(length).toBeLessThanOrEqual(160);
    });
  }

  it('uses the Chinese brand name on zh-HK home metadata', () => {
    const seo = getContent('zh-HK').seo;
    expect(seo.home.title).toContain('小天地 Siu Tin Dei');
    expect(seo.home.description).toContain('小天地 Siu Tin Dei');
    expect(seo.defaultSocialImageAlt).toContain('小天地 Siu Tin Dei');
  });

  it('emits Open Graph locales with the other locale as an alternate', () => {
    const metadata = buildLocalizedMetadata({
      locale: 'zh-HK',
      path: ROUTES.about,
      title: 'About',
      description: 'About the site',
      siteName: SITE_NAME,
      socialImage: { url: '/images/seo/siutindei-og-2026-11.jpg', alt: 'Share image' },
    });

    expect(metadata.openGraph).toMatchObject({ locale: 'zh_HK', alternateLocale: ['en_HK'] });
    expect(metadata.alternates?.languages).toMatchObject({
      en: expect.stringContaining('/en/about'),
      'zh-HK': expect.stringContaining('/zh-HK/about'),
    });
  });
});
