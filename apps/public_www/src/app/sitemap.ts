import type { MetadataRoute } from 'next';

import { SUPPORTED_LOCALES } from '@/content/locales';
import { listStaticActivityParams } from '@/lib/activities/static-activity-catalog';
import { localizePath } from '@/lib/locale-routing';
import { INDEXED_ROUTE_PATHS } from '@/lib/routes';
import { getSiteOrigin } from '@/lib/seo';

export const dynamic = 'force-static';

export default function sitemap(): MetadataRoute.Sitemap {
  const siteOrigin = getSiteOrigin();
  const now = new Date();

  const pages = SUPPORTED_LOCALES.flatMap((locale) =>
    INDEXED_ROUTE_PATHS.map((path) => ({
      url: `${siteOrigin}${localizePath(path, locale)}`,
      lastModified: now,
      changeFrequency: path === '/' ? 'weekly' as const : 'monthly' as const,
      priority: path === '/' ? 1 : 0.8,
    })),
  );
  const activities = listStaticActivityParams().map(({ locale, id }) => ({
    url: `${siteOrigin}${localizePath(`/activity/${id}`, locale)}`,
    lastModified: now,
    changeFrequency: 'weekly' as const,
    priority: 0.6,
  }));
  return [...pages, ...activities];
}
