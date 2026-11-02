import type { MetadataRoute } from 'next';

import { ROBOTS_DISALLOWED_PATHS } from '@/lib/routes';
import { getSiteHost, getSiteOrigin } from '@/lib/seo';

export const dynamic = 'force-static';

export default function robots(): MetadataRoute.Robots {
  const siteOrigin = getSiteOrigin();
  const siteHost = getSiteHost();

  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: [...ROBOTS_DISALLOWED_PATHS],
      },
    ],
    sitemap: `${siteOrigin}/sitemap.xml`,
    host: siteHost,
  };
}
