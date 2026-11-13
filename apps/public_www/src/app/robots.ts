import type { MetadataRoute } from 'next';

import {
  AI_SEARCH_USER_AGENTS,
  AI_TRAINING_USER_AGENTS,
  ROBOTS_DISALLOWED_PATHS,
} from '@/lib/routes';
import { getSiteOrigin } from '@/lib/seo';

export const dynamic = 'force-static';

export default function robots(): MetadataRoute.Robots {
  const siteOrigin = getSiteOrigin();

  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: [...ROBOTS_DISALLOWED_PATHS],
      },
      {
        userAgent: [...AI_SEARCH_USER_AGENTS],
        allow: '/',
        disallow: [...ROBOTS_DISALLOWED_PATHS],
      },
      {
        userAgent: [...AI_TRAINING_USER_AGENTS],
        disallow: '/',
      },
    ],
    sitemap: `${siteOrigin}/sitemap.xml`,
  };
}
